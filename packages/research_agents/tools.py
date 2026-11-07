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
from dataclasses import dataclass, field

from packages.contracts_lane_b import DEVELOPMENT_SPLITS, ExperimentResult, GateRunner

from .allowlist import check_gate
from .evidence import EvidenceStore
from .models import TrialRecord
from .news import NewsStore, as_utc


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


def _norm(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    return float(v)


def spec_hash(spec: dict) -> str:
    """Hash of what determines the decisions only (names and metadata excluded), so the same gate
    always gets the same hash and two different gates can never share one."""
    body = {k: v for k, v in spec.items() if k not in METADATA_KEYS}
    if isinstance(body.get("conditions"), list):
        body["conditions"] = [{k: _norm(x) for k, x in c.items()} if isinstance(c, dict) else c for c in body["conditions"]]
    for k in ("allocation_when_true", "allocation_when_false"):
        if k in body:
            body[k] = _norm(body[k])
    return "spec_" + hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:12]


def redact(exp: ExperimentResult) -> ExperimentResult:
    """Copy with every test-split row removed (windows kept, so guards know where test starts)."""
    return exp.model_copy(update={
        "per_regime": [r for r in exp.per_regime if r.split != "test"],
        "costs": [c for c in exp.costs if c.split != "test"],
        "baselines": [b for b in exp.baselines if b.split != "test"],
    })


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

    def __post_init__(self):
        self.experiment = redact(self.experiment)

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
            "note": "mean_net_return is per decision interval after costs; CI is Lane A's block bootstrap (90%). "
                    "Buckets with n_trades < 20 are fragile.",
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

    def development_end(self):
        val = [w for w in self.experiment.windows if w.split == "validation"]
        test = [w for w in self.experiment.windows if w.split == "test"]
        if not val or not test:
            return None                       # fail closed: without both windows we can't place the holdout
        return min(as_utc(val[0].end), as_utc(test[0].start))

    def news_context(self, start: str, end: str, decision_cutoff: str | None = None) -> dict:
        s, e = as_utc(start), as_utc(end)
        cutoff = as_utc(decision_cutoff) if decision_cutoff else e
        dev_end = self.development_end()
        if dev_end is None:
            raise HoldoutAccessError("validation/test windows unknown; news access is closed until Lane A provides them")
        if e > dev_end or cutoff > dev_end:
            raise HoldoutAccessError(f"news window or cutoff after the development end {dev_end.isoformat()}")
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

    def test_gate_train(self, policy_spec: dict) -> dict:
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
        return self._evaluate(policy_spec, "train", "agent")

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

    def _evaluate(self, policy_spec: dict, split: str, source: str) -> dict:
        pid, h = str(policy_spec.get("policy_id", "unnamed")), spec_hash(policy_spec)
        try:
            ev = self.gate_runner.evaluate(policy_spec, split)
        except Exception as exc:      # runner errors are logged, never silently dropped
            self._log(policy_id=pid, spec_hash=h, source=source, split=split, delta_net_return_vs_always_on=None,
                      ci_delta=None, evidence_id=None, status="error", note=f"{type(exc).__name__}: {exc}")
            return {"error": f"{type(exc).__name__}: {exc}"}
        payload = {"policy_spec": policy_spec, "spec_hash": h, "evaluation": ev.model_dump()}
        eid = self.store.add("test_gate_train" if split == "train" else "arbiter_evaluate", {"spec_hash": h, "split": split}, payload)
        self._log(policy_id=pid, spec_hash=h, source=source, split=split, delta_net_return_vs_always_on=ev.delta_net_return_vs_always_on,
                  ci_delta=ev.ci_delta, allocation_mix=ev.allocation_mix, evidence_id=eid, status="evaluated")
        return {"evidence_id": eid, **payload}

    def feature_grid(self) -> dict:
        """Allowed thresholds (training-quantile grid) per allowlisted feature, with coverage."""
        payload = {"train_quantiles": {f: {str(q): v for q, v in qs.items()} for f, qs in self.train_quantiles.items()},
                   "coverage": self.experiment.coverage}
        eid = self.store.add("feature_grid", {}, payload)
        return {"evidence_id": eid, **payload}
