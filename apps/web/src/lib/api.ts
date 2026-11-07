import { API_ROUTES } from "../../../../packages/contracts/api";
import type { Experiment, Health, ImportPreview, ImportRequest, ImportResult, PaperPlan, Strategy } from "../../../../packages/contracts/types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...options, cache: "no-store" });
  if (!response.ok) {
    let message = `Request failed (${response.status}). Please try again.`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((item: { msg: string }) => item.msg).join(". ");
    } catch { /* The proxy may respond with HTML when the API is offline. */ }
    if (response.status === 502 || response.status === 503) message = "The research service is unavailable. Check that the API is running and retry.";
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
function json(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}
export const api = {
  health: () => request<Health>(API_ROUTES.health),
  strategies: () => request<Strategy[]>(API_ROUTES.strategies),
  preview: (file: File) => { const data = new FormData(); data.append("file", file); return request<ImportPreview>(API_ROUTES.previewImport, { method: "POST", body: data }); },
  importStrategy: (data: ImportRequest) => request<ImportResult>(API_ROUTES.importStrategy, json(data)),
  experiments: (strategyId: string) => request<Experiment[]>(API_ROUTES.strategyExperiments(strategyId)),
  experiment: (id: string) => request<Experiment>(API_ROUTES.experiment(id)),
  investigate: (strategyId: string) => request<Experiment>(API_ROUTES.experiments, json({ strategy_id: strategyId })),
  paperPlans: () => request<PaperPlan[]>(API_ROUTES.paperPlans),
  freezePaperPlan: (experimentId: string) => request<PaperPlan>(API_ROUTES.paperPlans, json({ experiment_id: experimentId, duration_days: 14, approved: true })),
};
