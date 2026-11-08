/** Shared HTTP paths for Part C. Keep these aligned with apps/api/main.py. */
export const API_PREFIX = "/api";
export const DEFAULT_API_URL = "http://127.0.0.1:8000";
export const CONTRACT_VERSION = "1";

const id = (value: string) => encodeURIComponent(value);
export const API_ROUTES = {
  health: `${API_PREFIX}/health`,
  strategies: `${API_PREFIX}/strategies`,
  nativeReportExample: `${API_PREFIX}/examples/native-report`,
  strategyDefinitions: `${API_PREFIX}/strategies/definitions`,
  strategyDefinition: (strategyId: string) => `${API_PREFIX}/strategies/${id(strategyId)}/definition`,
  previewImport: `${API_PREFIX}/imports/preview`,
  importStrategy: `${API_PREFIX}/strategies/import`,
  strategyDefinitionTemplate: `${API_PREFIX}/templates/strategy-definition.json`,
  positionTemplate: `${API_PREFIX}/templates/positions.csv`,
  tradeTemplate: `${API_PREFIX}/templates/trades.csv`,
  experiments: `${API_PREFIX}/experiments`,
  strategyExperiments: (strategyId: string) => `${API_PREFIX}/experiments?strategy_id=${id(strategyId)}`,
  experiment: (experimentId: string) => `${API_PREFIX}/experiments/${id(experimentId)}`,
  experimentReport: (experimentId: string) => `${API_PREFIX}/experiments/${id(experimentId)}/report`,
  paperPlans: `${API_PREFIX}/paper-tests`,
  investigations: `${API_PREFIX}/investigations`,
  investigation: (experimentId: string) => `${API_PREFIX}/investigations/${id(experimentId)}`,
} as const;
