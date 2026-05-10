import { getJson, postJson } from "@/shared/api/http-client";

import type {
  SecurityActor,
  SecurityActorDetail,
  SecurityActorsQuery,
  SecurityBlock,
  SecurityEvent,
  SecurityPaginatedActors,
  SecuritySummary,
  SecurityTimeseries,
} from "@/features/backoffice/security/types/security.types";

export function getSecuritySummary(token: string): Promise<SecuritySummary> {
  return getJson<SecuritySummary>("/backoffice/security/summary/", undefined, { token });
}

export function getSecurityTimeseries(token: string): Promise<SecurityTimeseries> {
  return getJson<SecurityTimeseries>("/backoffice/security/timeseries/", undefined, { token });
}

export function getSecurityActors(token: string, params: SecurityActorsQuery): Promise<SecurityPaginatedActors> {
  return getJson<SecurityPaginatedActors>("/backoffice/security/actors/", params, { token });
}

export function getSecurityActorDetails(token: string, actorId: string): Promise<SecurityActorDetail> {
  return getJson<SecurityActorDetail>(`/backoffice/security/actors/${actorId}/`, undefined, { token });
}

export function getSecurityActorHistory(token: string, actorId: string): Promise<{ results: SecurityEvent[] }> {
  return getJson<{ results: SecurityEvent[] }>(`/backoffice/security/actors/${actorId}/history/`, undefined, { token });
}

export function releaseSecurityBlock(token: string, blockId: string, reason: string): Promise<SecurityBlock> {
  return postJson<SecurityBlock, { reason: string }>(`/backoffice/security/blocks/${blockId}/release/`, { reason }, undefined, { token });
}

export function createSecurityBlock(token: string, actorId: string, reason: string): Promise<SecurityBlock> {
  return postJson<SecurityBlock, { actor_id: string; reason: string }>("/backoffice/security/blocks/", { actor_id: actorId, reason }, undefined, { token });
}

export function whitelistSecurityBlock(token: string, blockId: string, reason: string): Promise<SecurityActor> {
  return postJson<SecurityActor, { reason: string }>(`/backoffice/security/blocks/${blockId}/whitelist/`, { reason }, undefined, { token });
}

export function extendSecurityBlock(token: string, blockId: string, minutes: number, reason: string): Promise<SecurityBlock> {
  return postJson<SecurityBlock, { minutes: number; reason: string }>(
    `/backoffice/security/blocks/${blockId}/extend/`,
    { minutes, reason },
    undefined,
    { token },
  );
}

export function addSecurityComment(token: string, actorId: string, comment: string): Promise<SecurityActor> {
  return postJson<SecurityActor, { comment: string }>(`/backoffice/security/actors/${actorId}/comment/`, { comment }, undefined, { token });
}

export function markSecurityActorFalsePositive(token: string, actorId: string, reason: string): Promise<SecurityActor> {
  return postJson<SecurityActor, { reason: string }>(`/backoffice/security/actors/${actorId}/false-positive/`, { reason }, undefined, { token });
}
