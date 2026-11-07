import { API_ROUTES } from "../../../../packages/contracts/api";
import type { InvestigationSummary, InvestigationWrapper } from "../../../../packages/contracts/research";
export type * from "../../../../packages/contracts/research";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    let detail = `Could not load investigation (${response.status}).`;
    try { const body = await response.json(); if (typeof body.detail === "string") detail = body.detail; } catch { /* preserve useful status text */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const teamApi = {
  investigations: () => request<InvestigationSummary[]>(API_ROUTES.investigations),
  investigation: (experimentId: string) => request<InvestigationWrapper>(API_ROUTES.investigation(experimentId)),
};
