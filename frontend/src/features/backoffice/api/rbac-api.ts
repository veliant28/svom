import { deleteJson, getJson, patchJson, postJson } from "@/shared/api/http-client";

import type {
  BackofficeGroupItem,
  BackofficeGroupWritePayload,
  BackofficeManagedUser,
  BackofficeManagedUserDetail,
  BackofficeManagedUserWritePayload,
  BackofficeRbacMeta,
} from "@/features/backoffice/types/rbac.types";

export async function getBackofficeRbacMeta(token: string): Promise<BackofficeRbacMeta> {
  return getJson<BackofficeRbacMeta>("/backoffice/rbac/meta/", undefined, { token });
}

export async function listBackofficeUsers(
  token: string,
  params: Partial<{ q: string; is_active: string; system_role: string; group_id: number; page: number }>,
): Promise<{ count: number; results: BackofficeManagedUser[] }> {
  return getJson<{ count: number; results: BackofficeManagedUser[] }>("/backoffice/users/", params, { token });
}

export async function createBackofficeUser(
  token: string,
  payload: BackofficeManagedUserWritePayload,
): Promise<BackofficeManagedUserDetail> {
  return postJson<BackofficeManagedUserDetail, BackofficeManagedUserWritePayload>("/backoffice/users/", payload, undefined, { token });
}

export async function getBackofficeUser(token: string, id: number): Promise<BackofficeManagedUserDetail> {
  return getJson<BackofficeManagedUserDetail>(`/backoffice/users/${id}/`, undefined, { token });
}

export async function updateBackofficeUser(
  token: string,
  id: number,
  payload: BackofficeManagedUserWritePayload,
): Promise<BackofficeManagedUserDetail> {
  return patchJson<BackofficeManagedUserDetail, BackofficeManagedUserWritePayload>(`/backoffice/users/${id}/`, payload, undefined, { token });
}

export async function activateBackofficeUser(token: string, id: number): Promise<BackofficeManagedUserDetail> {
  return postJson<BackofficeManagedUserDetail, Record<string, never>>(`/backoffice/users/${id}/activate/`, {}, undefined, { token });
}

export async function deactivateBackofficeUser(token: string, id: number): Promise<BackofficeManagedUserDetail> {
  return postJson<BackofficeManagedUserDetail, Record<string, never>>(`/backoffice/users/${id}/deactivate/`, {}, undefined, { token });
}

export async function deleteBackofficeUser(token: string, id: number): Promise<void> {
  return deleteJson<void>(`/backoffice/users/${id}/`, undefined, { token });
}

export async function listBackofficeGroups(
  token: string,
  params: Partial<{ q: string; page: number }>,
): Promise<{ count: number; results: BackofficeGroupItem[] }> {
  return getJson<{ count: number; results: BackofficeGroupItem[] }>("/backoffice/groups/", params, { token });
}

export async function createBackofficeGroup(token: string, payload: BackofficeGroupWritePayload): Promise<BackofficeGroupItem> {
  return postJson<BackofficeGroupItem, BackofficeGroupWritePayload>("/backoffice/groups/", payload, undefined, { token });
}

export async function getBackofficeGroup(token: string, id: number): Promise<BackofficeGroupItem> {
  return getJson<BackofficeGroupItem>(`/backoffice/groups/${id}/`, undefined, { token });
}

export async function updateBackofficeGroup(
  token: string,
  id: number,
  payload: BackofficeGroupWritePayload,
): Promise<BackofficeGroupItem> {
  return patchJson<BackofficeGroupItem, BackofficeGroupWritePayload>(`/backoffice/groups/${id}/`, payload, undefined, { token });
}
