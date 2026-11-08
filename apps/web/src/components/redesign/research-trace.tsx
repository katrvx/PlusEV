"use client";

import { Check, ChevronDown, CircleDashed, FileSearch, FlaskConical, X } from "lucide-react";
import type { Experiment, ResearchStep } from "../../../../../packages/contracts/types";
import type { TeamReport } from "../../../../../packages/contracts/research";
import "./research-trace.css";

type Props = {
  steps: ResearchStep[];
  mode: Experiment["mode"];
  /** Provenance is separate from display mode: real native reports may still
   * be presented as a demo because no measured Part C metrics are attached. */
  synthetic?: boolean;
  onEvidence: (id: string) => void;
};

export const statusCopy: Record<ResearchStep["status"], string> = {
  complete: "Checked",
  rejected: "Challenged",
  running: "In progress",
  pending: "Waiting",
};

const statusIcon = (status: ResearchStep["status"]) => {
  if (status === "complete") return <Check size={15} aria-hidden="true" />;
  if (status === "rejected") return <X size={15} aria-hidden="true" />;
  if (status === "running") return <FlaskConical size={15} aria-hidden="true" />;
  return <CircleDashed size={15} aria-hidden="true" />;
};

export function humanRole(role: string) {
  const value = role.trim();
  if (!value) return "Recorded step";
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

export function humanAction(action: string) {
  const value = action.trim();
  const known: Record<string, string> = {
    called_tool: "Checked the recorded output.",
    checked: "Checked the recorded output.",
    proposed: "Proposed a candidate rule.",
    analyzed: "Mapped the recorded findings.",
    challenged: "Challenged the candidate rule.",
    challenge: "Challenged the candidate rule.",
    code_check: "Checked the recorded output.",
    tool_call: "Checked the recorded output.",
    critic: "Challenged the candidate rule.",
    arbiter: "Applied the independent check.",
    rejected: "Rejected this explanation.",
    tested: "Tested the candidate rule.",
    selected: "Recorded the selected outcome.",
    qualified: "Qualified the recommendation.",
  };
  if (known[value.toLowerCase()]) return known[value.toLowerCase()];
  if (!value) return "Recorded a research step.";
  const sentence = value.replace(/[_-]+/g, " ");
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)}${/[.!?]$/.test(sentence) ? "" : "."}`;
}

function unique(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}

function reportEvidenceIds(report: TeamReport, values: string[]) {
  const known = new Set(report.evidence.map(item => item.evidence_id));
  return unique(values).filter(id => known.has(id)).slice(0, 1);
}

function firstReportEvidence(report: TeamReport, ...values: string[][]) {
  return reportEvidenceIds(report, values.flat());
}

function reportTool(report: TeamReport, evidenceIds: string[], fallback: string) {
  return report.evidence.find(item => item.evidence_id === evidenceIds[0])?.tool || fallback;
}

function nativeTraceStep(report: TeamReport, step: Omit<ResearchStep, "timestamp">): ResearchStep {
  return { ...step, timestamp: report.generated_at };
}

/**
 * Build the five judge-facing stages from the native report itself. The full
 * experiment step list remains the technical log; this is only a compact
 * reading path over recorded report fields, not a generated progress story.
 */
export function buildNativeTraceSteps(report: TeamReport): ResearchStep[] {
  const hypotheses = report.diagnostic.hypotheses || [];
  const proposals = report.proposals || [];
  const critiques = report.critiques || [];
  const trials = report.trial_log || [];
  const hypothesisEvidence = hypotheses.flatMap(item => item.evidence_ids || []);
  const proposalEvidence = proposals.flatMap(item => item.evidence_ids || []);
  const critiqueEvidence = critiques.flatMap(item => item.evidence_ids || []);
  const trialEvidence = trials.map(item => item.evidence_id || "");
  const selectedCandidate = report.candidates?.find(item => item.policy_id === report.champion_policy_id);
  const selectedEvidence = selectedCandidate?.evidence_ids || [];
  const arbiterEvidence = trials.filter(item => item.source === "arbiter").map(item => item.evidence_id || "");
  const healthEvidence = report.strategy_health?.evidence_id ? [report.strategy_health.evidence_id] : [];

  const approvedCritiques = critiques.filter(item => /approve|accept/i.test(item.verdict)).length;
  const rejectedCritiques = critiques.filter(item => /reject|veto/i.test(item.verdict)).length;
  const otherCritiques = Math.max(0, critiques.length - approvedCritiques - rejectedCritiques);
  const critiqueStatus: ResearchStep["status"] = critiques.length === 0
    ? "pending"
    : rejectedCritiques > 0
      ? "rejected"
      : "complete";
  const critiqueCounts = [
    `${approvedCritiques} approved`,
    `${rejectedCritiques} rejected`,
    ...(otherCritiques ? [`${otherCritiques} other`] : []),
  ].join(", ");
  const splitCounts = unique(["train", "validation", "test"].map(split => {
    const count = trials.filter(item => item.split === split).length;
    return count ? `${count} ${split}` : "";
  })).join(", ");
  const verdict = report.verdict || "INCONCLUSIVE";
  const holdoutCopy = report.holdout_accessed
    ? "Holdout access is recorded."
    : "Holdout was not accessed; the sealed look remains separate.";

  return [
    nativeTraceStep(report, {
      id: "native-stage-findings",
      role: "Research agent",
      action: "analyzed",
      title: `Research agent recorded ${hypotheses.length} ${hypotheses.length === 1 ? "finding" : "findings"}`,
      body: report.diagnostic.summary || `${hypotheses.length} diagnostic findings were recorded.`,
      status: hypotheses.length ? "complete" : "pending",
      tool: reportTool(report, firstReportEvidence(report, hypothesisEvidence, healthEvidence), "diagnostic"),
      evidence_ids: firstReportEvidence(report, hypothesisEvidence, healthEvidence),
    }),
    nativeTraceStep(report, {
      id: "native-stage-proposals",
      role: "Agent proposer",
      action: "proposed",
      title: `Agent proposed ${proposals.length} ${proposals.length === 1 ? "candidate rule" : "candidate rules"}`,
      body: proposals.length
        ? `Recorded families: ${unique(proposals.map(item => humanRole(item.family))).join(", ") || "not supplied"}.`
        : "No candidate proposals were recorded.",
      status: proposals.length ? "complete" : "pending",
      tool: reportTool(report, firstReportEvidence(report, proposalEvidence), "proposal record"),
      evidence_ids: firstReportEvidence(report, proposalEvidence),
    }),
    nativeTraceStep(report, {
      id: "native-stage-critique",
      role: "Independent critic",
      action: "challenged",
      title: `Critic reviewed ${critiques.length} ${critiques.length === 1 ? "proposal" : "proposals"}`,
      body: critiques.length ? `Recorded critic outcomes: ${critiqueCounts}.` : "No critic record was attached.",
      status: critiqueStatus,
      tool: critiqueEvidence.length ? "Linked code evidence" : "Critic record",
      evidence_ids: firstReportEvidence(report, critiqueEvidence),
    }),
    nativeTraceStep(report, {
      id: "native-stage-code-checks",
      role: "Code evaluator",
      action: "checked",
      title: `Code checked ${report.n_policies_tried} recorded ${report.n_policies_tried === 1 ? "policy" : "policies"}`,
      body: trials.length ? `${trials.length} trial ${trials.length === 1 ? "row" : "rows"} recorded${splitCounts ? ` across ${splitCounts}` : ""}.` : "No policy trial rows were recorded.",
      status: trials.length ? "complete" : "pending",
      tool: reportTool(report, firstReportEvidence(report, trialEvidence), "policy evaluator"),
      evidence_ids: firstReportEvidence(report, trialEvidence),
    }),
    nativeTraceStep(report, {
      id: "native-stage-outcome",
      role: "Recorded arbiter",
      action: report.champion_policy_id ? "selected" : "qualified",
      title: report.holdout_accessed ? "Recorded research outcome" : report.champion_policy_id ? "Recorded selection before the sealed look" : "Recorded outcome before the sealed look",
      body: `${report.champion_policy_id ? `Selected policy ${report.champion_policy_id}. ` : "No candidate policy was selected. "}Recorded verdict: ${humanRole(verdict)}. ${holdoutCopy}`,
      status: report.verdict || report.champion_policy_id ? "complete" : "pending",
      tool: reportTool(report, firstReportEvidence(report, selectedEvidence, arbiterEvidence, healthEvidence), "recorded outcome"),
      evidence_ids: firstReportEvidence(report, selectedEvidence, arbiterEvidence, healthEvidence),
    }),
  ];
}

function TraceStep({ step, index, expanded, onEvidence }: { step: ResearchStep; index: number; expanded: boolean; onEvidence: (id: string) => void }) {
  return <li className={`rt-step rt-${step.status}`}>
    <div className="rt-node" aria-hidden="true">{statusIcon(step.status)}</div>
    <details className="rt-detail" open={expanded}>
      <summary>
        <span className="rt-summary-copy">
          <span className="rt-step-number">CHECK {String(index + 1).padStart(2, "0")}</span>
          <strong>{step.title}</strong>
          <span className="rt-status">{statusCopy[step.status]} <span className="rt-role-separator" aria-hidden="true">·</span> {humanRole(step.role)}{step.evidence_ids.length > 0 && <><span className="rt-role-separator" aria-hidden="true"> · </span>{step.evidence_ids.length} {step.evidence_ids.length === 1 ? "source" : "sources"}</>}</span>
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </summary>
      <div className="rt-body">
        <p className="rt-action">{humanAction(step.action)}</p>
        {step.body?.trim() && step.body.trim().toLowerCase() !== step.action.trim().toLowerCase() && <p className="rt-context">{step.body}</p>}
        <dl className="rt-meta">
          <div><dt>Role</dt><dd>{humanRole(step.role)}</dd></div>
          <div><dt>Tool</dt><dd>{humanRole(step.tool)}</dd></div>
        </dl>
        {step.evidence_ids.length > 0 ? <div className="rt-links" aria-label="Recorded outputs">
          {step.evidence_ids.map(id => <button key={id} type="button" onClick={() => onEvidence(id)}><FileSearch size={14} aria-hidden="true" /><span>Open recorded output</span><code className="rt-output-id">{id}</code><span aria-hidden="true">↗</span></button>)}
        </div> : <p className="rt-no-links">No linked output was recorded for this step.</p>}
      </div>
    </details>
  </li>;
}

export default function ResearchTrace({ steps, mode, synthetic, onEvidence }: Props) {
  if (steps.length === 0) return null;
  const ordered = steps.slice(0, 5);
  const expandedIndex = Math.max(0, ordered.findIndex(step => step.status === "rejected"));
  const countLabel = ordered.length < steps.length
    ? `${ordered.length} of ${steps.length} steps`
    : `${ordered.length} ${ordered.length === 1 ? "step" : "steps"}`;
  const isSyntheticExample = synthetic === true || (synthetic === undefined && mode === "demo");
  return <section className="research-trace" data-guide-target="agent-trace" aria-labelledby="research-trace-title">
    <div className="rt-heading">
      <div>
        <span className="rt-eyebrow">RECORDED WORK</span>
        <h2 id="research-trace-title">How we reached this.</h2>
        <p>{isSyntheticExample ? "A recorded example of the checks behind the finding." : "A compact record of the checks behind this finding."} Agents propose; code checks the rule.</p>
      </div>
      <span className="rt-count">{countLabel}</span>
    </div>
    <ol className="rt-track" aria-label="Recorded research steps">
      {ordered.map((step, index) => <TraceStep key={step.id} step={step} index={index} expanded={index === expandedIndex} onEvidence={onEvidence} />)}
    </ol>
    <p className="rt-footnote"><span aria-hidden="true">↳</span> Open a step to see its check and linked evidence.</p>
  </section>;
}
