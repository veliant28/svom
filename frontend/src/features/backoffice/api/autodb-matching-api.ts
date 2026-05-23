import { getJson, postJson, type QueryParams } from "@/shared/api/http-client";

import type {
  AutoDbActionResponse,
  AutoDbDashboard,
  AutoDbJobDetail,
  AutoDbJobsResponse,
  AutoDbRemoteQuota,
  AutoDbSearchResponse,
  AutoDbSkuLookupResponse,
  AutoDbTecdocBatchStateResponse,
} from "@/features/backoffice/types/backoffice";

const BASE = "/backoffice/autodb-matching";

export function getAutoDbMatchingDashboard(token: string) {
  return getJson<AutoDbDashboard>(`${BASE}/dashboard/`, undefined, { token });
}

export function getAutoDbMatchingRemoteQuota(token: string) {
  return getJson<AutoDbRemoteQuota>(`${BASE}/remote-quota/`, undefined, { token });
}

export function getAutoDbMatchingJobs(token: string, params?: QueryParams) {
  return getJson<AutoDbJobsResponse>(`${BASE}/jobs/`, params, { token });
}

export function getAutoDbMatchingJob(token: string, id: string) {
  return getJson<AutoDbJobDetail>(`${BASE}/jobs/${id}/`, undefined, { token });
}

export function buildAutoDbJobsDryRun(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbActionResponse, Record<string, unknown>>(`${BASE}/build-jobs-dry-run/`, body, undefined, { token });
}

export function runAutoDbLocalDryRun(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbActionResponse, Record<string, unknown>>(`${BASE}/run-local-dry-run/`, body, undefined, { token });
}

export function runAutoDbRemote(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbActionResponse, Record<string, unknown>>(`${BASE}/run-remote/`, body, undefined, { token });
}

export function manualAutoDbSearchLocal(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbSearchResponse, Record<string, unknown>>(
    `${BASE}/manual-search/local/`,
    body,
    undefined,
    { token, timeoutMs: 45000 },
  );
}

export function manualAutoDbSearchRemote(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbSearchResponse, Record<string, unknown>>(
    `${BASE}/manual-search/remote/`,
    body,
    undefined,
    { token, timeoutMs: 180000 },
  );
}

export function createAutoDbMatchingJobDryRun(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbActionResponse, Record<string, unknown>>(`${BASE}/manual-search/create-job/`, body, undefined, { token });
}

export function lookupAutoDbMatchingProducts(token: string, params: { q: string; limit?: number }) {
  return getJson<AutoDbSkuLookupResponse>(`${BASE}/manual-search/product-lookup/`, params, { token });
}

export function planAutoDbCloneSync(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbActionResponse, Record<string, unknown>>(`${BASE}/plan-clone-sync/`, body, undefined, { token });
}

export function auditAutoDbLink(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbActionResponse, Record<string, unknown>>(`${BASE}/audit-link/`, body, undefined, { token });
}

export function planAutoDbSafeLink(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbActionResponse, Record<string, unknown>>(`${BASE}/plan-safe-link/`, body, undefined, { token });
}

export function planAutoDbEnrichment(token: string, body: Record<string, unknown>) {
  return postJson<AutoDbActionResponse, Record<string, unknown>>(`${BASE}/plan-enrichment/`, body, undefined, { token });
}

export function getAutoDbTecdocBatchState(token: string) {
  return getJson<AutoDbTecdocBatchStateResponse>(`${BASE}/tecdoc-batch/state/`, undefined, { token });
}

export function runAutoDbTecdocBatch(token: string, body: { batch_size: number; product_ids?: string[]; continuous?: boolean }) {
  return postJson<AutoDbActionResponse, { batch_size: number; product_ids?: string[]; continuous?: boolean }>(`${BASE}/tecdoc-batch/run/`, body, undefined, { token });
}

export function stopAutoDbTecdocBatch(token: string) {
  return postJson<AutoDbActionResponse, Record<string, never>>(`${BASE}/tecdoc-batch/stop/`, {}, undefined, { token });
}
