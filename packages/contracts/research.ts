/** Native Lane B investigation report shape consumed by Part C. */
export type AgentMode = "llm" | "llm_with_fallback" | "deterministic_fallback";

export type TeamEvidence = {
  evidence_id: string;
  tool: string;
  args: Record<string, unknown>;
  payload: Record<string, unknown>;
  created_at: string;
};
export type TeamHypothesis = {
  hypothesis_id: string;
  statement: string;
  direction: "works_better" | "works_worse";
  conditions: string[];
  evidence_ids: string[];
  confidence: "low" | "medium" | "high";
  caveats: string[];
  suggested_test: string;
};
export type TeamProposal = {
  proposal_id: string;
  family: string;
  based_on: string[];
  conditions: { feature: string; op: "<=" | ">"; threshold: number }[];
  allocation_when_true: number;
  allocation_when_false: number;
  rationale: string;
  evidence_ids: string[];
  falsification_test: string;
};
export type TeamTrial = {
  policy_id: string;
  spec_hash?: string | null;
  source: "agent" | "arbiter" | "rule_baseline" | "meta_model";
  split: "train" | "validation" | "test";
  delta_net_return_vs_always_on: number | null;
  ci_delta: [number, number] | null;
  allocation_mix?: Record<string, number>;
  evidence_id: string | null;
  status: "evaluated" | "refused" | "error";
  note: string;
};
export type TeamCandidate = {
  policy_id: string;
  spec_hash?: string | null;
  source: "agent" | "rule_baseline" | "meta_model";
  role?: "agent_champion" | "agent_not_selected" | "competitor";
  policy_spec: Record<string, unknown>;
  status: "accepted_for_frozen_test" | "rejected" | "competitor";
  validation_delta_vs_always_on?: number | null;
  validation_ci?: [number, number] | null;
  validation_delta_vs_simple_rule?: number | null;
  allocation_mix?: Record<string, number>;
  reasons: string[];
  evidence_ids: string[];
};
export type TeamReport = {
  experiment_id: string;
  strategy_id: string;
  generated_at: string;
  agent_mode: AgentMode;
  model_id: string | null;
  agent_failures?: string[];
  verdict?: "candidate_for_frozen_test" | "INCONCLUSIVE";
  champion_policy_id?: string | null;
  diagnostic: {
    summary: string;
    hypotheses: TeamHypothesis[];
    rejected_explanations: string[];
    limitations: string[];
  };
  proposals: TeamProposal[];
  critiques: { proposal_id: string; verdict: string; leakage_concerns: string[]; overfit_risks: string[]; fragile_samples: string[]; counterexamples: string[]; evidence_ids: string[] }[];
  trial_log: TeamTrial[];
  candidates: TeamCandidate[];
  test_requests: string[];
  limitations: string[];
  evidence: TeamEvidence[];
  n_distinct_agent_policies?: number;
  n_policies_tried: number;
  holdout_accessed: boolean;
};
export type InvestigationWrapper = { source: "team_artifact" | "bundled_lane_b_fixture"; synthetic: boolean; source_path: string; report: TeamReport };
export type InvestigationSummary = {
  experiment_id: string;
  strategy_id: string;
  generated_at: string;
  agent_mode: AgentMode;
  model_id: string | null;
  holdout_accessed: boolean;
  source: InvestigationWrapper["source"];
  synthetic: boolean;
  source_path: string;
  diagnostic_summary: string;
  hypothesis_count: number;
  proposal_count: number;
  trial_count: number;
  evidence_count: number;
  n_policies_tried: number;
};
