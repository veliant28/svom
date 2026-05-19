import { getJson, postJson } from "@/shared/api/http-client";
import { normalizePaginatedListResponse } from "@/shared/api/normalize-list-response";

import type { BackofficeReturnOperational, BackofficeReturnStatusUpdatePayload } from "@/features/backoffice/types/returns.types";
import type { BackofficeListQuery } from "@/features/backoffice/api/backoffice-api.types";

export async function getBackofficeReturns(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeReturnOperational[] | { results: BackofficeReturnOperational[]; count: number }>(
    "/backoffice/returns/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeReturnDetail(token: string, returnId: string): Promise<BackofficeReturnOperational> {
  return getJson<BackofficeReturnOperational>(`/backoffice/returns/${returnId}/`, undefined, { token });
}

export async function updateBackofficeReturnStatus(
  token: string,
  returnId: string,
  payload: BackofficeReturnStatusUpdatePayload,
): Promise<BackofficeReturnOperational> {
  return postJson<BackofficeReturnOperational, BackofficeReturnStatusUpdatePayload>(
    `/backoffice/returns/${returnId}/status/`,
    payload,
    undefined,
    { token },
  );
}
