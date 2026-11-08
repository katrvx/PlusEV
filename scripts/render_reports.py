"""Write a plain-language report per recorded run: experiments/readable/<strategy>.md (+ .json takeaway).

No agents run, nothing is recomputed, the held-out test is not touched: it formats what the committed reports and
the one held-out look already contain.  Run: python3 scripts/render_reports.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from packages.research_agents.recorded import RECORDED_RUNS, present_report  # noqa: E402

OUT = ROOT / "experiments" / "readable"


def _pct(x):
    return "Not recorded" if x is None else f"{x * 100:+.1f}%"


def _pp(x):
    return "Not recorded" if x is None else f"{x * 100:+.1f} pp"


def markdown(sid: str, p) -> str:
    h = p.headline
    lines = [f"# {p.takeaway.strategy.name or sid}", "",
             f"**Strategy verdict: {h.verdict_label}** — applies to {h.verdict_scope or 'Not recorded'}"
             + (f" ({h.verdict_source})" if h.verdict_source else ""), "",
             f"**Finding.** {h.finding}", "", f"**What it means.** {h.meaning}", "",
             f"**What to do next.** {h.next_action}", "", "## Research stages", "",
             "| Stage | Window | What happened | Result |", "|---|---|---|---|"]
    for s in p.stages:
        lines.append(f"| {s.stage} | {s.window} | {s.what_happened} | {s.result} |")
    lines += ["", "## Filters that were checked", "",
              "A filter only changes position size (none, half or full). Checked does not mean passed.", "",
              "| Filter | Proposed by | Checked in | Outcome | Validation vs original | Own return on Validation | Why |",
              "|---|---|---|---|---|---|---|"]
    for f in p.filters:
        if f.outcome == "not_run":
            continue
        lines.append(f"| {f.label} | {f.proposed_by} | {', '.join(f.stages_checked) or '—'} | **{f.outcome_label}** | "
                     f"{_pp(f.validation_vs_original_pp)} | {_pct(f.validation_own_return)} | {f.reason} |")
    nr = [f for f in p.filters if f.outcome == "not_run"]
    if nr:
        lines += ["", f"Also tried on Training only and not taken further ({len(nr)}): "
                  + "; ".join(f.label for f in nr) + "."]
    timed = [f for f in p.filters if f.timing]
    if timed:
        lines += ["", "## Timing or just less risk? (Validation, same costs)", "",
                  "| Filter | vs constant half size | vs constant at its Training size | vs constant at its Validation size | Read |", "|---|---|---|---|---|"]
        for f in timed:
            t = f.timing
            same = f"{_pp(t.vs_same_average_size_pp)} (constant {t.same_average_size:.2f}x)" if t.same_average_size is not None else _pp(t.vs_same_average_size_pp)
            vs = (f"{_pp(t.vs_validation_size_pp)} (constant {t.validation_size:.2f}x)" if t.validation_size is not None
                  else "Not recorded")
            lines.append(f"| {f.label} | {_pp(t.vs_half_size_pp)} | {same} | {vs} | {t.read} |")
        lines += ["", f"Source: `{timed[0].timing.source}`. Diagnostic only: the selection rule fixed before the run is unchanged."]
    champ = next((f for f in p.filters if f.held_out), None)
    if champ:
        lines += ["", "## The one held-out look", "", champ.held_out.summary,
                  f"Source: `{champ.held_out.source}`." if champ.held_out.source else ""]
    lines += ["", "## How the agents got there", ""]
    for t in p.trace:
        lines.append(f"{t.step}. **{t.actor}** ({t.actor_kind}) — {t.title}. {t.summary}")
        for i in t.items[:4]:
            lines.append(f"   - {i}")
        if t.changed_conclusion:
            lines.append(f"   - *Changed the conclusion:* {t.changed_conclusion}")
    tk = p.takeaway
    lines += ["", "## Take away", "", f"**Strategy.** {tk.strategy.note}"]
    if tk.strategy.rule:
        lines += [f"- Rule: {tk.strategy.rule}", f"- Parameters: `{json.dumps(tk.strategy.parameters)}`",
                  f"- Source: `{tk.strategy.source}`"]
    lines += ["", f"**Selected filter.** {tk.selected_filter_note}"]
    if tk.selected_filter:
        lines += [f"- {tk.selected_filter['label']}: {tk.selected_filter['plain_rule']}",
                  f"- Status: {tk.selected_filter['status']}",
                  f"- Exact settings: `{json.dumps(tk.selected_filter['spec'])}`"]
    lines += ["", "**Evidence.**"] + [f"- {e['label']}: `{e.get('path') or e.get('evidence_id')}`" for e in tk.evidence]
    lines += ["", tk.plans, "", "---", f"*{p.generated_by}.*", ""]
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for sid, run in RECORDED_RUNS.items():
        report = json.loads((ROOT / run["report"]).read_text())
        p = present_report(report, run["report"])
        (OUT / f"{sid}.md").write_text(markdown(sid, p))
        (OUT / f"{sid}.json").write_text(json.dumps(p.model_dump(mode="json"), indent=1, ensure_ascii=False) + "\n")
        print(f"wrote experiments/readable/{sid}.md and .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
