"""The four allowlisted tools (AGENTS.md Lane B step 2), plus the arbiter's evaluation path.

    regime_performance   conditional performance of the unchanged strategy, per regime bucket
    cost_attribution     where the gap between gross and net comes from, plus baselines
    news_context         point-in-time news in a window, with coverage
    test_gate_train      evaluate an allowlisted gate on TRAIN via Lane A (agents)
    arbiter_evaluate     evaluate a policy on VALIDATION (code only, never exposed to agents)

Guardrails enforced in code, not in prompts:
- the test split is unreachable from every tool (HoldoutAccessError); the ExperimentResult
  given to agents is redacted to train/validation rows;
- every output is stored in the EvidenceStore and returned with its evidence_id;
- test_gate_train refuses specs outside the allowlist, has its own agent budget, and logs
  EVERY attempt; arbiter runs never consume the agent budget;
- trial records carry a spec hash, so two specs with the same name can never be confused;
- no tool executes uploaded code or touches strategy code.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from dataclasses import dataclass, field

from packages.contracts_lane_b import DEVELOPMENT_SPLITS, ExperimentResult, GateRunner

from .allowlist import check_gate
from .evidence import EvidenceStore
from .models import TrialRecord
from .news import NewsStore, as_utc


FOLD_NOTE = "walk-forward fold"   # TrialRecord.note prefix for arbiter fold runs (split "train")


def is_fold(trial) -> bool:
    return getattr(trial, "fold", None) is not None or str(getattr(trial, "note", "")).startswith(FOLD_NOTE)


class HoldoutAccessError(PermissionError):
    pass


def _guard(split) -> str:
    """Exact-match whitelist. Anything resembling 'test' is a holdout attempt; other junk is a plain error."""
    if split in DEVELOPMENT_SPLITS:
        return split
    if isinstance(split, str) and split.strip().lower() == "test":
        raise HoldoutAccessError(f"split '{split}' is sealed; agents may only use {DEVELOPMENT_SPLITS}")
    raise ValueError(f"unknown split {split!r}; use one of {DEVELOPMENT_SPLITS}")


METADATA_KEYS = {"policy_id", "thresholds_selected_on"}


def round_sig(x, sig: int = 12):
    """Round floats to `sig` significant digits so hashes/ids are identical across machines."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return x
    x = float(x)
    if x == 0 or not math.isfinite(x):
        return x
    return round(x, sig - 1 - int(math.floor(math.log10(abs(x)))))


def canonical(obj):
    if isinstance(obj, dict):
        return {k: canonical(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [canonical(v) for v in obj]
    return round_sig(obj)


def spec_hash(spec: dict) -> str:
    """Hash of what determines the decisions only (names/metadata excluded; floats rounded; conditions
    sorted; a single '>' condition rewritten as the equivalent '<=' with swapped allocations), so the
    same gate always gets the same hash and two different gates never share one."""
    body = canonical({k: v for k, v in spec.items() if k not in METADATA_KEYS})
    for k in ("allocation_when_true", "allocation_when_false"):
        if k in body and isinstance(body[k], (int, float)) and not isinstance(body[k], bool):
            body[k] = float(body[k])
    conds = body.get("conditions")
    if isinstance(conds, list) and all(isinstance(c, dict) for c in conds):
        if len(conds) == 1 and conds[0].get("op") == ">" and "allocation_when_true" in body:
            conds = [{**conds[0], "op": "<="}]
            body["allocation_when_true"], body["allocation_when_false"] = body["allocation_when_false"], body["allocation_when_true"]
        body["conditions"] = sorted(conds, key=lambda c: json.dumps(c, sort_keys=True, default=str))
    return "spec_" + hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:12]


def normalise_quantiles(tq: dict) -> dict[str, dict[float, float]]:
    """Accept quantile keys as floats or strings (JSON); return {feature: {0.5: value, ...}}."""
    out = {}
    for f, qs in tq.items():
        out[f] = {round(float(q), 4): float(v) for q, v in qs.items()}
    if 0.5 not in out.get("realized_vol_7d", {}):
        raise ValueError("train_quantiles must include the realized_vol_7d median (quantile 0.5) for the simple rule baseline")
    return out


def redact(exp: ExperimentResult) -> ExperimentResult:
    """Copy with every test-split row removed (windows kept, so guards know where test starts)."""
    update = {
        "per_regime": [r for r in exp.per_regime if r.split != "test"],
        "costs": [c for c in exp.costs if c.split != "test"],
        "baselines": [b for b in exp.baselines if b.split != "test"],
    }
    for name in ("equity", "comparison_equity"):        # Lane A's dev view already strips these; belt and braces
        rows = getattr(exp, name, None)
        if rows:
            update[name] = [r for r in rows if getattr(r, "split", None) != "test"]
    if getattr(exp, "notes", None):                     # Lane A's notes can quote the sealed-test verdict; agents never need them
        update["notes"] = []
    return exp.model_copy(update=update)


@dataclass
class ToolContext:
    experiment: ExperimentResult
    gate_runner: GateRunner
    news: NewsStore | None
    train_quantiles: dict[str, dict[float, float]]   # feature -> {quantile: value}, TRAIN window only (Lane A)
    store: EvidenceStore = field(default_factory=EvidenceStore)
    trials: list[TrialRecord] = field(default_factory=list)
    max_agent_gate_tests: int = 12                    # budget for AGENT train tests only
    holdout_accessed: bool = False
    stage: int = 0                                    # bumped when an agent stage ends; late tool results become 'abandoned'
    inflight: int = 0
    health: dict | None = None                        # code-computed bad-luck-vs-broken check (critic only; reads validation)
    folds_status: str | None = None                   # None (not tried) / "missing" (runner has no evaluate_folds) / "ran"
    fold_errors: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        self.experiment = redact(self.experiment)
        self.train_quantiles = normalise_quantiles(self.train_quantiles)

    # ------------------------------------------------------------------ stage bookkeeping (timeouts)

    def enter_tool(self) -> int:
        with self._lock:
            self.inflight += 1
            return self.stage

    def exit_tool(self) -> None:
        with self._lock:
            self.inflight -= 1

    def close_stage(self) -> None:
        with self._lock:
            self.stage += 1

    def wait_inflight(self, timeout_s: float = 10.0) -> int:
        """Wait for agent tool calls still running after a stage ended; return how many are still running."""
        t0 = time.monotonic()
        while self.inflight > 0 and time.monotonic() - t0 < timeout_s:
            time.sleep(0.05)
        return self.inflight

    def _log(self, **kw) -> None:
        self.trials.append(TrialRecord(**kw))

    def agent_tests_used(self) -> int:
        return sum(t.source == "agent" and t.split == "train" for t in self.trials)

    # ------------------------------------------------------------------ tools

    def regime_performance(self, split: str = "train", regime_feature: str | None = None) -> dict:
        split = _guard(split)
        rows = [r.model_dump() for r in self.experiment.per_regime
                if r.split == split and (regime_feature is None or r.regime_feature == regime_feature)]
        payload = {
            "split": split,
            "rows": rows,
            "n_buckets_scanned": len(rows),
            "note": "mean_net_return is per decision interval after costs; CI is Lane A's block bootstrap (90%). "
                    "Buckets with n_trades < 20 are fragile. Several buckets are scanned at once: no multiple-comparison correction.",
        }
        eid = self.store.add("regime_performance", {"split": split, "regime_feature": regime_feature}, payload)
        return {"evidence_id": eid, **payload}

    def cost_attribution(self, split: str = "train") -> dict:
        split = _guard(split)
        costs = [c.model_dump() for c in self.experiment.costs if c.split == split]
        baselines = [b.model_dump() for b in self.experiment.baselines if b.split == split]
        payload = {"split": split, "costs": costs, "baselines": baselines}
        eid = self.store.add("cost_attribution", {"split": split}, payload)
        return {"evidence_id": eid, **payload}

    def train_end(self):
        tr = [w for w in self.experiment.windows if w.split == "train"]
        return as_utc(tr[0].end) if tr else None

    def development_end(self):
        val = [w for w in self.experiment.windows if w.split == "validation"]
        test = [w for w in self.experiment.windows if w.split == "test"]
        if not val or not test:
            return None                       # fail closed: without both windows we can't place the holdout
        return min(as_utc(val[0].end), as_utc(test[0].start))

    def news_context(self, start: str, end: str, decision_cutoff: str | None = None, agent: bool = False) -> dict:
        """agent=True caps the window at the END OF TRAIN (agents are train-only); the arbiter may read validation news."""
        s, e = as_utc(start), as_utc(end)
        cutoff = as_utc(decision_cutoff) if decision_cutoff else e
        dev_end = self.development_end()
        if dev_end is None:
            raise HoldoutAccessError("validation/test windows unknown; news access is closed until Lane A provides them")
        if e > dev_end or cutoff > dev_end:
            raise HoldoutAccessError(f"news window or cutoff after the development end {dev_end.isoformat()}")
        if agent:
            tr_end = self.train_end()
            if tr_end is None or e > tr_end or cutoff > tr_end:
                raise ValueError(f"agents may only read news up to the end of train ({tr_end.isoformat() if tr_end else 'unknown'})")
        if s > e:
            raise ValueError("start must be before end")
        if self.news is None:
            payload = {"records": [], "coverage": {"records_in_window": 0}, "note": "no news source configured"}
        else:
            recs = self.news.visible(s, e, cutoff, symbol=None)
            payload = {
                "window": [s.isoformat(), e.isoformat()], "decision_cutoff": cutoff.isoformat(),
                "records": [r.model_dump(mode="json") for r in recs[:40]],
                "coverage": self.news.coverage(s, e),
                "note": "Contextual evidence only; co-occurrence with losses is not causation.",
            }
        eid = self.store.add("news_context", {"start": s.isoformat(), "end": e.isoformat(), "cutoff": cutoff.isoformat()}, payload)
        return {"evidence_id": eid, **payload}

    def test_gate_train(self, policy_spec: dict, stage_token: int | None = None) -> dict:
        """AGENT path: train only, allowlisted threshold gates only, budgeted, logged."""
        pid = str(policy_spec.get("policy_id", "unnamed"))
        h = spec_hash(policy_spec)
        if self.agent_tests_used() >= self.max_agent_gate_tests:
            self._log(policy_id=pid, spec_hash=h, source="agent", split="train", delta_net_return_vs_always_on=None,
                      ci_delta=None, evidence_id=None, status="refused", note="agent gate-test budget exhausted")
            return {"refused": ["agent gate-test budget exhausted"], "budget": self.max_agent_gate_tests}
        if policy_spec.get("family") != "threshold_gate":
            problems = ["agents may only test the threshold_gate family"]
        else:
            problems = check_gate(policy_spec.get("conditions"), policy_spec.get("allocation_when_true"),
                                  policy_spec.get("allocation_when_false"), self.experiment.coverage, self.train_quantiles)
        if problems:
            self._log(policy_id=pid, spec_hash=h, source="agent", split="train", delta_net_return_vs_always_on=None,
                      ci_delta=None, evidence_id=None, status="refused", note="; ".join(problems))
            return {"refused": problems}
        return self._evaluate(policy_spec, "train", "agent", stage_token)

    def arbiter_evaluate(self, policy_spec: dict, split: str, source: str = "arbiter") -> dict:
        """CODE path (never exposed to agents): no agent budget, no grid restriction, still logged."""
        try:
            split = _guard(split)
        except HoldoutAccessError as exc:
            self.holdout_accessed = True
            self._log(policy_id=str(policy_spec.get("policy_id", "unnamed")), spec_hash=spec_hash(policy_spec), source=source,
                      split="test", delta_net_return_vs_always_on=None, ci_delta=None, evidence_id=None, status="refused", note=str(exc))
            raise
        return self._evaluate(policy_spec, split, source)

    def attempt_holdout(self, policy_id: str, source: str = "agent") -> None:
        """Record an agent's attempt to reach the test split (called by tool wrappers)."""
        self.holdout_accessed = True
        self._log(policy_id=policy_id, source=source, split="test", delta_net_return_vs_always_on=None, ci_delta=None,
                  evidence_id=None, status="refused", note="holdout access attempt")

    def _evaluate(self, policy_spec: dict, split: str, source: str, stage_token: int | None = None) -> dict:
        pid, h = str(policy_spec.get("policy_id", "unnamed")), spec_hash(policy_spec)
        try:
            ev = self.gate_runner.evaluate(policy_spec, split)
        except Exception as exc:      # runner errors are logged, never silently dropped
            self._log(policy_id=pid, spec_hash=h, source=source, split=split, delta_net_return_vs_always_on=None,
                      ci_delta=None, evidence_id=None, status="error", note=f"{type(exc).__name__}: {exc}")
            return {"error": f"{type(exc).__name__}: {exc}"}
        payload = {"policy_spec": policy_spec, "spec_hash": h, "evaluation": ev.model_dump()}
        eid = self.store.add("test_gate_train" if split == "train" else "arbiter_evaluate", {"spec_hash": h, "split": split}, payload)
        late = stage_token is not None and stage_token != self.stage
        self._log(policy_id=pid, spec_hash=h, source=source, split=split, delta_net_return_vs_always_on=ev.delta_net_return_vs_always_on,
                  ci_delta=ev.ci_delta, net_return=ev.metrics.net_return, allocation_mix=ev.allocation_mix, evidence_id=eid,
                  status="error" if late else "evaluated",
                  note="abandoned: finished after its agent stage had ended (timeout); disclosed, not used" if late else "")
        return {"evidence_id": eid, **payload}

    def arbiter_folds(self, policy_spec: dict, source: str = "arbiter") -> list[dict]:
        """CODE path (never exposed to agents): score a frozen spec on Lane A's expanding TRAIN folds.

        Uses GateRunner.evaluate_folds when the loader provides it (Lane A does; the stand-in does not).
        Gate thresholds are quantiles of the whole train window, so folds are a stability check over
        train sub-periods, not unseen data. Every fold is logged and stored as citable evidence."""
        fn = getattr(self.gate_runner, "evaluate_folds", None)
        if fn is None:
            self.folds_status = self.folds_status or "missing"
            return []
        pid, h = str(policy_spec.get("policy_id", "unnamed")), spec_hash(policy_spec)
        try:
            evs = fn(policy_spec)
        except Exception as exc:      # noqa: BLE001 - logged, never silently dropped
            self._log(policy_id=pid, spec_hash=h, source=source, split="train", delta_net_return_vs_always_on=None,
                      ci_delta=None, evidence_id=None, status="error", fold=None,
                      note=f"{FOLD_NOTE}s failed: {type(exc).__name__}: {exc}")
            self.fold_errors += 1
            return []
        self.folds_status = "ran"
        out = []
        for ev in evs:
            k = getattr(ev, "fold", None)
            payload = {"policy_spec": policy_spec, "spec_hash": h, "fold": k, "evaluation": ev.model_dump()}
            eid = self.store.add("walk_forward_fold", {"spec_hash": h, "fold": k}, payload)
            self._log(policy_id=pid, spec_hash=h, source=source, split="train",
                      delta_net_return_vs_always_on=ev.delta_net_return_vs_always_on, ci_delta=ev.ci_delta,
                      net_return=ev.metrics.net_return, allocation_mix=ev.allocation_mix, evidence_id=eid,
                      status="evaluated", fold=k, note=f"{FOLD_NOTE} {k} (train sub-period; stability check, not unseen data)")
            out.append({"evidence_id": eid, **payload})
        return out

    def feature_grid(self) -> dict:
        """Allowed thresholds (training-quantile grid) per allowlisted feature, with coverage."""
        payload = {"train_quantiles": {f: {str(q): v for q, v in qs.items()} for f, qs in self.train_quantiles.items()},
                   "coverage": self.experiment.coverage}
        eid = self.store.add("feature_grid", {}, payload)
        return {"evidence_id": eid, **payload}
