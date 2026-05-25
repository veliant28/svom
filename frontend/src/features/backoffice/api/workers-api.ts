import { getJson, postJson } from "@/shared/api/http-client";

import type {
  BackofficeWorkerAction,
  BackofficeWorkerActionResponse,
  BackofficeWorkersDashboard,
} from "@/features/backoffice/types/worker-monitor.types";

const BASE = "/backoffice/workers";

export function getBackofficeWorkersDashboard(token: string) {
  return getJson<BackofficeWorkersDashboard>(`${BASE}/dashboard/`, undefined, { token });
}

export function runBackofficeWorkerAction(
  token: string,
  payload: { action: BackofficeWorkerAction; worker?: string; task_id?: string; queues?: string[] },
) {
  return postJson<BackofficeWorkerActionResponse, typeof payload>(`${BASE}/action/`, payload, undefined, { token });
}
