import type { Experiment, Strategy, PaperPlan, Health, Evidence, EquityPoint } from "../../../../../packages/contracts/types";
export type { Experiment, Strategy, PaperPlan, Health, Evidence, EquityPoint };
export type MainView = "strategy" | "explore" | "compare" | "observe";
export type ExploreTab = "overview" | "conditions" | "evidence";
export type MotionPreference = "system" | "reduced" | "full";
export type SharedResearchProps = {
  experiment: Experiment;
  strategy: Strategy;
  selectedDate: string | null;
  onSelectDate: (date: string | null) => void;
  onEvidence: (id: string) => void;
};
export type ChartSeries = "base" | "rule" | "proposed" | "cash";
export type ResearchChartProps = {
  data: EquityPoint[];
  series?: ChartSeries[];
  selectedDate?: string | null;
  onSelectDate?: (date: string | null) => void;
  label?: string;
  mode?: Experiment["mode"];
  height?: number;
  reveal?: boolean;
  compact?: boolean;
};
