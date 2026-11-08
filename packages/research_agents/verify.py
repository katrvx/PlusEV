"""Claim verification shared by the LLM output validators and the deterministic fallback.

Every text field an agent writes is checked, not just the headline statement:
- every number must be COPIED from the evidence the claim cites (print rounding only;
  '%' means /100 and 'bp' means /10,000, nothing else is rescaled);
- integers above 10 must equal a count that appears in the evidence exactly;
- an explicit sign (+/-) must match the evidence; unsigned numbers compare by magnitude;
- zeros in the evidence never 'support' anything; numbers written as words (above ten),
  multiples like '3.5x', durations like '73h' / '5d' and basis points are numbers too and are checked;
- the only free-standing label allowed is the CI level '90%' (all Lane A intervals are 90%);
- numbers the agent was GIVEN rather than measured are allowed too: whole numeric tokens of the strategy
  id/version (e.g. '24' and '72' in 'btc-trend-24-72-demo'), and MIN_TRADES only when quoted as a threshold
  ('fewer than 20 trades');
- rounding for print is fine (3-4 significant digits) but a number may differ from its evidence by at most
  1% of its size; a written zero needs an exact zero in the evidence; '.5', Unicode minus signs and
  e-notation integers ('2e2') are numbers like any other.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation

from .models import CritiqueSet, DiagnosticReport, ProposalSet

CI_LEVEL = 90
MIN_TRADES = 20          # 'treat buckets with fewer than 20 trades as weak' (agent instructions)
TRIVIAL_INTS = set(range(0, 11)) | {100}
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?\b")
NUM_RE = re.compile(r"(?<![A-Za-z_\d.])([-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(%|bps|bp|x|h|d)?(?![A-Za-z_\d])")
DASHES = str.maketrans({"\u2212": "-", "\u2013": "-", "\u2014": "-", "\u2012": "-", "\ufe63": "-", "\uff0d": "-"})
# the instruction threshold may be quoted as a threshold ("fewer than 20 trades", "<20 trades"), not as a measurement
THRESHOLD_RE = re.compile(r"(?:\b(?:fewer than|less than|under|below|at least|minimum of|min\.?)\s*|[<>]=?\s*|\u2265\s*|\u2264\s*)"
                          rf"{MIN_TRADES}(?![\d.])(?=\s*(?:trades?\b|$|[).,;]))", re.I)
NUM_KEY_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
REL_TOL = 0.01           # a copied number may differ from the evidence by print rounding AND by at most 1% of its size
WORD_NUM_RE = re.compile(r"\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
                         r"fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|percent)\b", re.I)


def _collect(obj, floats: list[float], ints: set[int], zero: list[bool]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)) and obj == 0:
        zero[0] = True                     # a written zero needs an exact zero; zeros never support other numbers
        return
    if isinstance(obj, int):
        ints.add(abs(obj))
        floats.append(float(obj))
    elif isinstance(obj, float):
        if math.isfinite(obj):
            floats.append(obj)
            if obj == int(obj):
                ints.add(abs(int(obj)))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and NUM_KEY_RE.fullmatch(k):   # quantile levels / allocation keys ('0.33', '0.5') are tool output too
                _collect(float(k), floats, ints, zero)
            elif isinstance(k, (int, float)) and not isinstance(k, bool):
                _collect(k, floats, ints, zero)
            _collect(v, floats, ints, zero)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, floats, ints, zero)


def unsupported_numbers(text: str, payloads: list) -> list[str]:
    """Number tokens in `text` that are not copied from `payloads`."""
    if not text:
        return []
    floats: list[float] = []
    ints: set[int] = set()
    zero = [False]
    _collect(payloads, floats, ints, zero)
    text = text.translate(DASHES)          # a Unicode minus must not hide a sign
    bad = [m.group(0) for m in WORD_NUM_RE.finditer(text)]
    clean = THRESHOLD_RE.sub(" ", DATE_RE.sub(" ", text))
    for m in NUM_RE.finditer(clean):
        raw, unit = m.group(1), (m.group(2) or "").lower()
        try:
            d = Decimal(raw)
        except InvalidOperation:
            continue
        val = float(d)
        signed = raw[0] in "+-"
        mantissa = raw.lower().split("e")[0]
        is_int = d == d.to_integral_value() and "." not in mantissa      # '2e2' is the integer 200
        if unit == "%" and val == CI_LEVEL:
            continue
        if unit in ("", "h", "d") and is_int:      # '73h' is the integer 73 with a unit
            if abs(int(val)) in TRIVIAL_INTS or abs(int(val)) in ints:
                continue
            bad.append(m.group(0).strip())
            continue
        if val == 0:
            if not zero[0]:
                bad.append(m.group(0).strip())
            continue
        scale = {"%": 100.0, "bp": 1e4, "bps": 1e4}.get(unit, 1.0)
        target = val / scale
        tol = 0.5 * 10 ** d.as_tuple().exponent / scale
        ok = False
        for v in floats:
            ref = v if signed else abs(v)
            t = target if signed else abs(target)
            if abs(ref - t) <= min(tol, REL_TOL * abs(ref)) + 1e-12 * abs(ref):
                ok = True
                break
        if not ok:
            bad.append(m.group(0).strip())
    return bad


def context_numbers(ctx) -> dict:
    """Numbers the agents were given in their prompt/instructions, not measured by a tool."""
    exp = ctx.experiment
    label = f"{getattr(exp, 'strategy_id', '')} {getattr(exp, 'strategy_version', '')}"
    # whole hyphen/space-separated tokens only ('24' and '72' in 'btc-trend-24-72-demo', '24' in '...-24h-...'), never fragments of ids or hashes
    return {"strategy_label_numbers": [float(x) for x in re.findall(r"(?<![A-Za-z0-9._])\d+(?:\.\d+)?(?=[hd]?(?![A-Za-z0-9_]))", label)]}


def _payloads(ctx, ids: list[str]) -> list:
    return [ctx.store.get(e).payload for e in ids if e in ctx.store] + [context_numbers(ctx)]


def _check_texts(label: str, texts: list[str], payloads: list) -> list[str]:
    bad = sorted({tok for t in texts for tok in unsupported_numbers(t, payloads)})
    return [f"{label}: numbers {bad} are not copied from the cited evidence (copy digits from the cited tool output; rounding to 3-4 significant digits is fine; all CIs are 90%)"] if bad else []


def verify_diagnostic(ctx, out: DiagnosticReport) -> list[str]:
    problems = []
    for h in out.hypotheses:
        missing = ctx.store.missing(h.evidence_ids)
        if missing:
            problems.append(f"{h.hypothesis_id}: unknown evidence ids {missing}")
            continue
        cited = _payloads(ctx, h.evidence_ids)
        rows = {f"{r['regime_feature']}={r['bucket']}": r for p in cited for r in p.get("rows", [])}
        bad_conds = [c for c in h.conditions if c not in rows]
        if bad_conds:
            problems.append(f"{h.hypothesis_id}: conditions {bad_conds} are not regime buckets in the cited regime_performance rows {sorted(rows)}")
        if h.confidence == "high":
            for c in h.conditions:
                r = rows.get(c)
                if r and not abs(r["mean_net_return"]) > (r["ci_high"] - r["ci_low"]):
                    problems.append(f"{h.hypothesis_id}: confidence 'high' needs |mean| larger than the CI width for {c}; use 'medium' or 'low'")
        problems += _check_texts(h.hypothesis_id, [h.statement, h.suggested_test, *h.caveats], cited)
    everything = [e.payload for e in ctx.store.all()] + [context_numbers(ctx)]
    problems += _check_texts("summary/rejected/limitations", [out.summary, *out.rejected_explanations, *out.limitations], everything)
    return problems


def verify_proposals(ctx, out: ProposalSet, hypothesis_ids: set[str]) -> list[str]:
    from .allowlist import check_gate
    problems = []
    for p in out.proposals:
        missing = ctx.store.missing(p.evidence_ids)
        if missing:
            problems.append(f"{p.proposal_id}: unknown evidence ids {missing}")
        unknown = set(p.based_on) - hypothesis_ids
        if unknown:
            problems.append(f"{p.proposal_id}: based_on refers to unknown hypotheses {sorted(unknown)}; valid: {sorted(hypothesis_ids)}")
        issues = check_gate([c.model_dump() for c in p.conditions], p.allocation_when_true, p.allocation_when_false,
                            ctx.experiment.coverage, ctx.train_quantiles)
        if issues:
            problems.append(f"{p.proposal_id} violates the allowlist: {issues}. Call feature_grid and use its thresholds.")
        problems += _check_texts(p.proposal_id, [p.rationale, p.falsification_test], _payloads(ctx, p.evidence_ids))
    return problems


def verify_critiques(ctx, out: CritiqueSet, proposals: ProposalSet) -> list[str]:
    from .tools import spec_hash
    problems = []
    by_id = {p.proposal_id: spec_hash(p.to_policy_spec()) for p in proposals.proposals}
    seen = {c.proposal_id for c in out.critiques}
    if seen != set(by_id):
        problems.append(f"critique exactly these proposals: {sorted(by_id)} (got {sorted(seen)})")
    for c in out.critiques:
        missing = ctx.store.missing(c.evidence_ids)
        if missing:
            problems.append(f"{c.proposal_id}: unknown evidence ids {missing}")
            continue
        h = by_id.get(c.proposal_id)
        if h and not any(ctx.store.get(e).payload.get("spec_hash") == h for e in c.evidence_ids):
            problems.append(f"{c.proposal_id}: cite at least one evaluation of this exact gate (see trial_log evidence_id)")
        if c.verdict == "approve_for_frozen_test" and c.fragile_samples:
            problems.append(f"{c.proposal_id}: 'approve' with entries in fragile_samples is contradictory; fragile_samples are BLOCKING. "
                            "Move non-blocking remarks to observations, or change the verdict.")
        problems += _check_texts(c.proposal_id, [*c.leakage_concerns, *c.overfit_risks, *c.fragile_samples, *c.counterexamples,
                                                 *c.observations], _payloads(ctx, c.evidence_ids))
    return problems
