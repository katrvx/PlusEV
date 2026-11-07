"""The four allowlisted tools (AGENTS.md Lane B step 2).

    regime_performance   conditional performance of the unchanged strategy, per regime bucket
    cost_attribution     where the gap between gross and net comes from, plus baselines
    news_context         point-in-time news in a window, with coverage
    test_gate_train      evaluate an allowlisted gate on TRAIN or VALIDATION via Lane A

Guardrails enforced in code, not in prompts:
- the test split is unreachable from every tool (HoldoutAccessError);
- every output is stored in the EvidenceStore and returned with its evidence_id;
- test_gate_train refuses specs outside the allowlist and logs EVERY attempt, refused or not;
- no tool executes uploaded code or touches strategy code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from packages.contracts_lane_b import DEVELOPMENT_SPLITS, ExperimentResult, GateRunner

from .allowlist import check_gate
from .evidence import EvidenceStore
from .models import TrialRecord
from .news import NewsStore


class HoldoutAccessError(PermissionError):
    pass


def _guard(split: str) -> None:
    if split not in DEVELOPMENT_SPLITS:
        raise HoldoutAccessError(f"split '{split}' is sealed; agents may only use {DEVELOPMENT_SPLITS}")


@dataclass
class ToolContext:
    experiment: ExperimentResult
    gate_runner: GateRunner
    news: NewsStore | None
    train_quantiles: dict[str, dict[float, float]]   # feature -> {quantile: value}, TRAIN window only (Lane A)
    store: EvidenceStore = field(default_factory=EvidenceStore)
    trials: list[TrialRecord] = field(default_factory=list)
    max_gate_tests: int = 12                          # budget: stops an agent from grid-searching
    holdout_accessed: bool = False

    # ------------------------------------------------------------------ tools

    def regime_performance(self, split: str = "train", regime_feature: str | None = None) -> dict:
        _guard(split)
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
        _guard(split)
        costs = [c.model_dump() for c in self.experiment.costs if c.split == split]
        baselines = [b.model_dump() for b in self.experiment.baselines if b.split == split]
        payload = {"split": split, "costs": costs, "baselines": baselines}
        eid = self.store.add("cost_attribution", {"split": split}, payload)
        return {"evidence_id": eid, **payload}

    def news_context(self, start: str, end: str, decision_cutoff: str | None = None) -> dict:
        s, e = datetime.fromisoformat(start), datetime.fromisoformat(end)
        cutoff = datetime.fromisoformat(decision_cutoff) if decision_cutoff else e
        test_windows = [w for w in self.experiment.windows if w.split == "test"]
        if any(e >= w.start for w in test_windows):
            raise HoldoutAccessError("news window reaches into the sealed test period")
        if self.news is None:
            payload = {"records": [], "coverage": {"records_in_window": 0}, "note": "no news source configured"}
        else:
            recs = self.news.visible(s, e, cutoff, symbol=None)
            payload = {
                "window": [start, end], "decision_cutoff": cutoff.isoformat(),
                "records": [r.model_dump(mode="json") for r in recs[:40]],
                "coverage": self.news.coverage(s, e),
                "note": "Contextual evidence only; co-occurrence with losses is not causation.",
            }
        eid = self.store.add("news_context", {"start": start, "end": end, "cutoff": cutoff.isoformat()}, payload)
        return {"evidence_id": eid, **payload}

    def test_gate_train(self, policy_spec: dict, split: str = "train", source: str = "agent") -> dict:
        pid = policy_spec.get("policy_id", "unnamed")
        try:
            _guard(split)
        except HoldoutAccessError as exc:
            self.holdout_accessed = True          # an ATTEMPT is recorded; nothing is returned
            self.trials.append(TrialRecord(policy_id=pid, source=source, split="validation", delta_net_return_vs_always_on=None,
                                           ci_delta=None, evidence_id=None, status="refused", note=str(exc)))
            raise
        if sum(t.status != "refused" for t in self.trials) >= self.max_gate_tests:
            self.trials.append(TrialRecord(policy_id=pid, source=source, split=split, delta_net_return_vs_always_on=None,
                                           ci_delta=None, evidence_id=None, status="refused", note="gate-test budget exhausted"))
            return {"refused": "gate-test budget exhausted", "budget": self.max_gate_tests}
        if policy_spec.get("family") == "threshold_gate":
            problems = check_gate(policy_spec.get("conditions", []), policy_spec.get("allocation_when_true"),
                                  policy_spec.get("allocation_when_false"), self.experiment.coverage, self.train_quantiles)
            if problems:
                self.trials.append(TrialRecord(policy_id=pid, source=source, split=split, delta_net_return_vs_always_on=None,
                                               ci_delta=None, evidence_id=None, status="refused", note="; ".join(problems)))
                return {"refused": problems}
        ev = self.gate_runner.evaluate(policy_spec, split)
        payload = {"policy_spec": policy_spec, "evaluation": ev.model_dump()}
        eid = self.store.add("test_gate_train", {"policy_id": pid, "split": split}, payload)
        self.trials.append(TrialRecord(policy_id=pid, source=source, split=split,
                                       delta_net_return_vs_always_on=ev.delta_net_return_vs_always_on,
                                       ci_delta=ev.ci_delta, evidence_id=eid, status="evaluated"))
        return {"evidence_id": eid, **payload}

    def feature_grid(self) -> dict:
        """Allowed thresholds (training-quantile grid) per allowlisted feature, with coverage."""
        payload = {"train_quantiles": {f: {str(q): v for q, v in qs.items()} for f, qs in self.train_quantiles.items()},
                   "coverage": self.experiment.coverage}
        eid = self.store.add("feature_grid", {}, payload)
        return {"evidence_id": eid, **payload}
