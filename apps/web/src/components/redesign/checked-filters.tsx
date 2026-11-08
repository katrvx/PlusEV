"use client";

import { useEffect, useState } from "react";
import { Check, ChevronRight, Download, FileJson, Info, ListChecks, Search, TriangleAlert } from "lucide-react";
import type { Experiment, Strategy } from "./types";
import type { TeamCandidate, TeamReport, TeamTrial } from "../../../../../packages/contracts/research";
import { downloadStrategyReviewPackage, type StrategyReviewFilterExport } from "../../lib/strategy-review-export";
import "./checked-filters.css";

export type CheckedFiltersProps = {
  experiment: Experiment;
  strategy: Strategy;
  onEvidence: (id: string) => void;
};

type FilterRow = {
  policyId: string;
  policyIds: string[];
  label: string;
  source: string;
  role: TeamCandidate["role"] | null;
  status: string;
  statusTone: "selected" | "neutral" | "caution" | "rejected";
  historicalSelection: boolean;
  specHash: string | null;
  policySpec: Record<string, unknown> | null;
  reasons: string[];
  evidenceIds: string[];
  trialRows: TeamTrial[];
  hasExecutableSource: boolean;
};

const sourceLabel = (source: string) => {
  if (source === "agent") return "Agent proposal";
  if (source === "arbiter") return "Evaluator check";
  if (source === "rule_baseline") return "Rule baseline";
  if (source === "meta_model") return "Model baseline";
  return source || "Recorded policy";
};

const titleCase = (value: string) => value
  .replace(/([a-z])([A-Z])/g, "$1 $2")
  .replace(/[_-]+/g, " ")
  .replace(/\s+/g, " ")
  .trim()
  .replace(/^./, letter => letter.toUpperCase());

const formatNumber = (value: number) => value.toLocaleString("en-GB", { useGrouping: false, maximumFractionDigits: 6 });

function humanFeature(value: unknown) {
  return typeof value === "string" ? titleCase(value) : "Condition";
}

function humanCondition(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  const feature = item.feature ?? item.field ?? item.name;
  const operator = item.op ?? item.operator;
  const threshold = item.threshold ?? item.value;
  if (feature !== undefined && operator !== undefined && typeof threshold === "number") return `${humanFeature(feature)} ${String(operator)} ${formatNumber(threshold)}`;
  if (feature !== undefined && operator !== undefined && threshold !== undefined) return `${humanFeature(feature)} ${String(operator)} ${String(threshold)}`;
  if (typeof item.description === "string") return item.description;
  return null;
}

function specDescription(spec: Record<string, unknown> | null) {
  if (!spec) return { conditions: [], allocation: null, caveat: "No executable rule text was supplied; this record preserves a filter proposal and its evidence only." };

  const rawConditions = spec.conditions ?? spec.rules ?? spec.filters ?? spec.predicates ?? spec.condition;
  const conditions = Array.isArray(rawConditions)
    ? rawConditions.map(humanCondition).filter((item): item is string => Boolean(item))
    : rawConditions ? [humanCondition(rawConditions)].filter((item): item is string => Boolean(item)) : [];
  const bucketText = (value: unknown) => Array.isArray(value)
    ? value.map(item => {
      if (!item || typeof item !== "object") return null;
      const record = item as Record<string, unknown>;
      return typeof record.axis === "string" && typeof record.bucket === "string" ? `${humanFeature(record.axis)} = ${record.bucket}` : null;
    }).filter((item): item is string => Boolean(item)).join(", ")
    : "";
  const flatBuckets = bucketText(spec.flat_buckets);
  const fullBuckets = bucketText(spec.full_buckets);
  if (flatBuckets) conditions.push(`Flat allocation in ${flatBuckets}`);
  if (fullBuckets) conditions.push(`Full allocation in ${fullBuckets}`);
  if (typeof spec.summary === "string" && spec.summary.trim()) conditions.push(spec.summary);
  if (Array.isArray(spec.features) && spec.features.length > 0) {
    const features = spec.features.filter((item): item is string => typeof item === "string").map(humanFeature);
    if (features.length > 0) conditions.push(`Recorded features: ${features.join(", ")}`);
  }
  const trueAllocation = spec.allocation_when_true ?? spec.position_when_true;
  const falseAllocation = spec.allocation_when_false ?? spec.position_when_false;
  let allocation: string | null = null;
  if (typeof trueAllocation === "number" || typeof falseAllocation === "number") {
    const whenTrue = typeof trueAllocation === "number" ? `${formatNumber(trueAllocation * 100)}% invested` : "the supplied allocation";
    const whenFalse = typeof falseAllocation === "number" ? `${formatNumber(falseAllocation * 100)}% invested` : "the supplied fallback";
    allocation = `When the condition matches: ${whenTrue}. Otherwise: ${whenFalse}.`;
  } else if (typeof spec.allocation === "string") {
    allocation = spec.allocation;
  } else if (typeof spec.allocation_flat === "number" || typeof spec.allocation_full === "number" || typeof spec.allocation_else === "number") {
    const flat = typeof spec.allocation_flat === "number" ? `${formatNumber(spec.allocation_flat * 100)}%` : "the supplied flat allocation";
    const full = typeof spec.allocation_full === "number" ? `${formatNumber(spec.allocation_full * 100)}%` : "the supplied full allocation";
    const otherwise = typeof spec.allocation_else === "number" ? `${formatNumber(spec.allocation_else * 100)}%` : "the supplied fallback";
    allocation = `Flat case: ${flat}; full case: ${full}; otherwise: ${otherwise}.`;
  }
  if (conditions.length === 0 && typeof spec.description === "string") conditions.push(spec.description);
  if (conditions.length === 0 && typeof spec.family === "string") conditions.push(`${titleCase(spec.family)} filter`);
  return { conditions, allocation, caveat: null };
}

function policyName(spec: Record<string, unknown> | null, fallback: string) {
  if (!spec) return fallback;
  const conditions = spec.conditions ?? spec.rules ?? spec.filters ?? spec.predicates;
  const first = Array.isArray(conditions) ? conditions[0] : conditions;
  if (first && typeof first === "object") {
    const feature = (first as Record<string, unknown>).feature ?? (first as Record<string, unknown>).field;
    if (typeof feature === "string") return `${humanFeature(feature)} filter`;
  }
  if (typeof spec.summary === "string" && spec.summary.trim()) return titleCase(String(spec.family ?? "Regime")) + " filter";
  if (typeof spec.family === "string") return `${titleCase(spec.family)} filter`;
  return fallback;
}

function candidateStatus(candidate: TeamCandidate | undefined, isChampion: boolean, hasFrozenMatch: boolean) {
  if (isChampion && hasFrozenMatch) return { label: "Research only · not approved", tone: "caution" as const };
  if (candidate?.status === "accepted_for_frozen_test") return { label: "Selected for sealed look · not approved", tone: "selected" as const };
  if (candidate?.status === "rejected") return { label: "Rejected during research", tone: "rejected" as const };
  if (candidate?.status === "competitor") return { label: "Benchmark candidate", tone: "neutral" as const };
  if (candidate?.role === "agent_not_selected") return { label: "Agent candidate · not selected", tone: "neutral" as const };
  return { label: isChampion ? "Recorded champion selection" : "Recorded check", tone: "neutral" as const };
}

function filterRows(report: TeamReport, strategy: Strategy, experiment: Experiment): FilterRow[] {
  const byId = new Map<string, FilterRow>();
  const bySpecHash = new Map<string, FilterRow>();
  const candidateById = new Map(report.candidates.map(candidate => [candidate.policy_id, candidate]));
  const hasFrozen = (policyId: string) => Boolean(experiment.frozen_evaluation?.evaluation.policy_id === policyId);
  const upsert = (policyId: string, seed?: Partial<FilterRow>) => {
    if (!policyId) return undefined;
    const candidate = candidateById.get(policyId);
    const specHash = candidate?.spec_hash ?? seed?.specHash ?? null;
    const current = byId.get(policyId) ?? (specHash ? bySpecHash.get(specHash) : undefined);
    if (current) {
      if (!current.policyIds.includes(policyId)) current.policyIds.push(policyId);
      byId.set(policyId, current);
      if (specHash) bySpecHash.set(specHash, current);
      return current;
    }
    const champion = report.champion_policy_id === policyId;
    const state = candidateStatus(candidate, champion, hasFrozen(policyId));
    const row: FilterRow = {
      policyId,
      policyIds: [policyId],
      label: champion ? "Selected filter" : candidate?.role === "competitor" ? "Benchmark" : sourceLabel(candidate?.source ?? seed?.source ?? "Recorded policy"),
      source: candidate?.source ?? seed?.source ?? "recorded",
      role: candidate?.role ?? null,
      status: state.label,
      statusTone: state.tone,
      historicalSelection: champion,
      specHash,
      policySpec: candidate?.policy_spec ?? seed?.policySpec ?? null,
      reasons: candidate?.reasons ? [...candidate.reasons] : [],
      evidenceIds: candidate?.evidence_ids ? [...candidate.evidence_ids] : [],
      trialRows: [],
      hasExecutableSource: Boolean(strategy.definition),
    };
    row.label = champion
      ? `Selected · ${policyName(row.policySpec, "filter")}`
      : candidate?.role === "competitor"
        ? policyName(row.policySpec, "Benchmark")
        : policyName(row.policySpec, sourceLabel(row.source));
    byId.set(policyId, row);
    if (specHash) bySpecHash.set(specHash, row);
    return row;
  };

  report.candidates.forEach(candidate => upsert(candidate.policy_id));
  report.trial_log.forEach(trial => {
    const row = upsert(trial.policy_id, { source: trial.source, specHash: trial.spec_hash });
    if (!row) return;
    row.trialRows.push(trial);
    if (trial.spec_hash && !row.specHash) row.specHash = trial.spec_hash;
    if (trial.evidence_id && !row.evidenceIds.includes(trial.evidence_id)) row.evidenceIds.push(trial.evidence_id);
  });

  // Some train-only policies are represented only by an arbiter evidence row.
  // Recover their exact recorded spec without inventing one from a return value.
  for (const row of byId.values()) {
    const evidence = report.evidence.filter(item => row.evidenceIds.includes(item.evidence_id));
    for (const item of evidence) {
      const payload = item.payload as Record<string, unknown>;
      const spec = payload.policy_spec;
      if (!row.policySpec && spec && typeof spec === "object" && !Array.isArray(spec)) row.policySpec = spec as Record<string, unknown>;
      if (!row.specHash && typeof payload.spec_hash === "string") row.specHash = payload.spec_hash;
      if (row.specHash && !bySpecHash.has(row.specHash)) bySpecHash.set(row.specHash, row);
    }
    if (!candidateById.has(row.policyId) && row.trialRows.length > 0) {
      const statuses = new Set(row.trialRows.map(trial => trial.status));
      if (statuses.has("evaluated")) row.status = "Recorded check";
      else if (statuses.has("error")) { row.status = "Error recorded"; row.statusTone = "caution"; }
      else row.status = "Not run · refused request";
    }
  }

  const priority = (row: FilterRow) => {
    if (row.historicalSelection) return 0;
    if (row.source === "agent" || row.role === "agent_champion" || row.role === "agent_not_selected") return 1;
    if (row.source === "rule_baseline" || row.source === "meta_model" || row.role === "competitor") return 2;
    return 3;
  };
  return [...new Set(byId.values())].sort((a, b) => priority(a) - priority(b) || a.policyId.localeCompare(b.policyId));
}

function legacyRow(experiment: Experiment, strategy: Strategy): FilterRow {
  const pending = experiment.mode === "pending" || experiment.status === "awaiting_engine" || experiment.status === "queued" || experiment.status === "running";
  const demo = experiment.mode === "demo" || strategy.status === "demo";
  const status = demo ? "Illustrative example · not measured" : pending ? "Pending evaluation" : "Recorded rule · review evidence";
  return {
    policyId: experiment.policy_id,
    policyIds: [experiment.policy_id],
    label: "Supplied strategy rule",
    source: "legacy experiment",
    role: null,
    status,
    statusTone: demo || pending ? "neutral" : "caution",
    historicalSelection: false,
    specHash: null,
    policySpec: { description: experiment.policy.description, conditions: experiment.policy.conditions, holdout_frozen: experiment.policy.holdout_frozen, test_evaluated: experiment.policy.test_evaluated },
    reasons: [],
    evidenceIds: [],
    trialRows: [],
    hasExecutableSource: Boolean(strategy.definition),
  };
}

function policyExport(row: FilterRow): StrategyReviewFilterExport {
  return {
    policyId: row.policyId,
    policyIds: row.policyIds,
    specHash: row.specHash,
    policySpec: row.policySpec,
    status: row.status,
    historicalSelection: row.historicalSelection,
    evidenceIds: row.evidenceIds,
    reasons: row.reasons,
    trialRows: row.trialRows,
  };
}

function splitLabel(split: TeamTrial["split"]) {
  return split === "test" ? "new-data test" : split;
}

function FilterDetail({ row, strategy, onEvidence, onDownload }: { row: FilterRow; strategy: Strategy; onEvidence: (id: string) => void; onDownload: () => void }) {
  const description = specDescription(row.policySpec);
  const splits = [...new Set(row.trialRows.map(trial => splitLabel(trial.split)))];
  return <section className="cf-detail" aria-labelledby="cf-detail-title">
    <div className="cf-detail-topline"><span className={`cf-status cf-status-${row.statusTone}`}>{row.statusTone === "selected" ? <Check size={14} aria-hidden="true" /> : row.statusTone === "rejected" ? <TriangleAlert size={14} aria-hidden="true" /> : <Info size={14} aria-hidden="true" />}{row.status}</span><span className="cf-detail-source">{sourceLabel(row.source)}</span></div>
    <h3 id="cf-detail-title">What this filter says</h3>
    {description.conditions.length > 0 ? <ul className="cf-condition-list">{description.conditions.map(condition => <li key={condition}>{condition}</li>)}</ul> : <p className="cf-empty-copy">No plain-language condition was recorded for this policy.</p>}
    {description.allocation && <p className="cf-allocation"><strong>Allocation</strong>{description.allocation}</p>}
    <p className="cf-detail-note">{row.hasExecutableSource ? "This is a recorded proposal attached to the supplied strategy definition; the package below is still a review record, not an execution order." : "This review preserves a filter proposal and its evidence. The supplied strategy contains positions or metadata rather than executable source, so this is not a runnable bot."}</p>
    <div className="cf-id-grid"><div><span>Policy ID</span><code>{row.policyId}</code></div><div><span>Spec hash</span><code>{row.specHash ?? "Not supplied"}</code></div><div><span>Recorded checks</span><strong>{row.trialRows.length || "None"}{splits.length > 0 && <small> · {splits.join(", ")}</small>}</strong></div></div>
    {row.evidenceIds.length > 0 && <div className="cf-evidence"><span className="cf-mini-label">Evidence for this filter</span><div className="cf-evidence-links">{row.evidenceIds.map(id => <button type="button" key={id} onClick={() => onEvidence(id)}><Search size={14} aria-hidden="true" /><code>{id}</code><ChevronRight size={14} aria-hidden="true" /></button>)}</div></div>}
    <details className="cf-spec-details"><summary><FileJson size={14} aria-hidden="true" />Show exact policy specification and recorded rationale</summary><div className="cf-raw-section"><div>{row.policyIds.length > 1 && <><span className="cf-mini-label">Policy IDs sharing this spec</span><ul className="cf-reasons">{row.policyIds.map(id => <li key={id}><code>{id}</code></li>)}</ul></>}{row.reasons.length > 0 && <><span className="cf-mini-label">Recorded reasons</span><ul className="cf-reasons">{row.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></>}{row.trialRows.length > 0 && <><span className="cf-mini-label">Trial rows</span><div className="cf-trial-list">{row.trialRows.map((trial, index) => <div className="cf-trial-row" key={`${trial.policy_id}-${trial.split}-${index}`}><span><strong>{splitLabel(trial.split)}</strong><small>{trial.status} · {trial.source}</small></span><code>{trial.evidence_id ?? "No evidence ID"}</code></div>)}</div></>}</div><pre>{JSON.stringify(row.policySpec ?? { policy_id: row.policyId, note: "No exact policy specification supplied" }, null, 2)}</pre></div></details>
    <div className="cf-detail-actions"><button type="button" className="cf-download" onClick={onDownload}><Download size={15} aria-hidden="true" />Download strategy review package</button><span>Includes the original strategy identity, selected filter, IDs, and matching frozen evidence when supplied.</span></div>
  </section>;
}

export function CheckedFilters({ experiment, strategy, onEvidence }: CheckedFiltersProps) {
  const report = experiment.native_report;
  const rows = report ? filterRows(report, strategy, experiment) : [legacyRow(experiment, strategy)];
  const [selectedId, setSelectedId] = useState(rows[0]?.policyId ?? "");
  const selected = rows.find(row => row.policyId === selectedId) ?? rows[0];
  useEffect(() => {
    if (rows.length > 0 && !rows.some(row => row.policyId === selectedId)) setSelectedId(rows[0].policyId);
  }, [rows, selectedId]);
  if (!selected) return null;
  const policyCount = report ? report.n_policies_tried : 1;
  const trialCount = report ? report.trial_log.length : 0;
  const download = () => { downloadStrategyReviewPackage({ experiment, strategy, selectedFilter: policyExport(selected) }); };

  return <section className="cf-shell" aria-labelledby="cf-title" data-guide-target="checked-filters">
    <div className="cf-heading"><div><span className="cf-eyebrow"><ListChecks size={14} aria-hidden="true" />CHECKED FILTERS</span><h2 id="cf-title">What rules were actually checked?</h2><p>Start with the selected result, then inspect the exact filter and its supporting record.</p></div><div className="cf-counts" aria-label={report ? `${policyCount} policies reported and ${trialCount} trial rows` : "One supplied strategy rule"}><strong>{report ? policyCount : "1"}</strong><span>{report ? "policies reported" : "supplied rule"}</span>{report && <><strong>{trialCount}</strong><span>trial rows</span></>}</div></div>
    {report && <p className="cf-count-note"><Info size={14} aria-hidden="true" />The supplied policy count is separate from trial rows. Trial rows can include evaluated, refused, or error requests; they are not a pass/fail score.</p>}
    {report && !report.champion_policy_id && <p className="cf-no-selection"><TriangleAlert size={15} aria-hidden="true" /><span>No filter was selected for a sealed look in this report. The first recorded policy is shown for inspection only.</span></p>}
    <div className="cf-layout"><nav className="cf-list" aria-label="Checked filters"><div className="cf-list-label">Filters in the record</div>{rows.map(row => <button type="button" key={row.policyId} className={row.policyId === selected.policyId ? "cf-filter-button is-selected" : "cf-filter-button"} aria-current={row.policyId === selected.policyId ? "true" : undefined} onClick={() => setSelectedId(row.policyId)}><span className="cf-filter-copy"><strong>{row.label}</strong><small>{row.policyId}</small></span><span className={`cf-filter-status cf-filter-status-${row.statusTone}`} title={row.status}>{row.statusTone === "selected" ? "Selected" : row.statusTone === "rejected" ? "Rejected" : row.statusTone === "caution" ? "Review only" : row.role === "competitor" ? "Benchmark" : "Recorded"}</span><ChevronRight size={16} aria-hidden="true" /></button>)}</nav><FilterDetail row={selected} strategy={strategy} onEvidence={onEvidence} onDownload={download} /></div>
  </section>;
}

export default CheckedFilters;
