import { getJson, postJson } from "@/shared/api/http-client";

import type {
  SupportBootstrap,
  SupportCounters,
  SupportMessagesPage,
  SupportQueueSnapshot,
  SupportThread,
  SupportThreadFilters,
  SupportThreadStatus,
  SupportUser,
  SupportWallboardSnapshot,
} from "@/features/support/types";

type SupportScope = "storefront" | "backoffice";

function scopeBase(scope: SupportScope): string {
  return scope === "backoffice" ? "/backoffice/support" : "/commerce/support";
}

function threadParams(filters: SupportThreadFilters): Record<string, string | number | boolean | undefined> {
  return {
    status: filters.status,
    assigned_to_me: filters.assigned_to_me,
    unassigned: filters.unassigned,
    waiting: filters.waiting,
    search: filters.search,
    ordering: filters.ordering,
    limit: filters.limit,
    thread_id: filters.thread_id,
  };
}

export async function getSupportBootstrap(token: string, scope: SupportScope, filters: SupportThreadFilters = {}): Promise<SupportBootstrap> {
  return getJson<SupportBootstrap>(`${scopeBase(scope)}/bootstrap/`, threadParams(filters), { token });
}

export async function getSupportThreads(token: string, scope: SupportScope, filters: SupportThreadFilters = {}): Promise<{ results: SupportThread[] }> {
  return getJson<{ results: SupportThread[] }>(`${scopeBase(scope)}/threads/`, threadParams(filters), { token });
}

export async function createSupportThread(token: string, payload: { subject: string; body: string }): Promise<SupportThread> {
  return postJson<SupportThread, { subject: string; body: string }>("/commerce/support/threads/", payload, undefined, { token });
}

export async function getSupportThread(token: string, scope: SupportScope, threadId: string): Promise<SupportThread> {
  return getJson<SupportThread>(`${scopeBase(scope)}/threads/${threadId}/`, undefined, { token });
}

export async function getSupportMessages(
  token: string,
  scope: SupportScope,
  threadId: string,
  params?: { before_message_id?: string; limit?: number },
): Promise<SupportMessagesPage> {
  return getJson<SupportMessagesPage>(`${scopeBase(scope)}/threads/${threadId}/messages/`, params, { token });
}

export async function postSupportMessage(
  token: string,
  scope: SupportScope,
  threadId: string,
  body: string,
): Promise<SupportMessagesPage> {
  return postJson<SupportMessagesPage, { body: string }>(`${scopeBase(scope)}/threads/${threadId}/messages/`, { body }, undefined, { token });
}

export async function markSupportThreadRead(token: string, scope: SupportScope, threadId: string): Promise<{ thread_id: string; last_read_message_id: string | null; last_read_at: string | null }> {
  return postJson<{ thread_id: string; last_read_message_id: string | null; last_read_at: string | null }, Record<string, never>>(
    `${scopeBase(scope)}/threads/${threadId}/read/`,
    {},
    undefined,
    { token },
  );
}

export async function updateSupportThreadStatus(token: string, threadId: string, status: SupportThreadStatus): Promise<SupportThread> {
  return postJson<SupportThread, { status: SupportThreadStatus }>(`/backoffice/support/threads/${threadId}/status/`, { status }, undefined, { token });
}

export async function assignSupportThread(token: string, threadId: string, assignedStaffId: number): Promise<SupportThread> {
  return postJson<SupportThread, { assigned_staff_id: number }>(
    `/backoffice/support/threads/${threadId}/assign/`,
    { assigned_staff_id: assignedStaffId },
    undefined,
    { token },
  );
}

export async function getSupportQueue(token: string): Promise<SupportQueueSnapshot> {
  return getJson<SupportQueueSnapshot>("/backoffice/support/queue/", undefined, { token });
}

export async function getSupportCounters(token: string): Promise<SupportCounters> {
  return getJson<SupportCounters>("/backoffice/support/counters/", undefined, { token });
}

export async function getSupportWallboard(token: string): Promise<SupportWallboardSnapshot> {
  return getJson<SupportWallboardSnapshot>("/backoffice/support/wallboard/", undefined, { token });
}

export async function getSupportStaffOptions(token: string): Promise<{ results: SupportUser[] }> {
  return getJson<{ results: SupportUser[] }>("/backoffice/support/staff/", undefined, { token });
}
