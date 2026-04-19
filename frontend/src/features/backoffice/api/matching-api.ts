import { getJson, postJson } from "@/shared/api/http-client";
import { normalizePaginatedListResponse } from "@/shared/api/normalize-list-response";

import type { BackofficeMatchingCandidateProduct, BackofficeMatchingSummary, BackofficeRawOffer } from "@/features/backoffice/types/backoffice";

import type { BackofficeListQuery } from "./backoffice-api.types";

export async function getBackofficeMatchingSummary(token: string): Promise<BackofficeMatchingSummary> {
  return getJson<BackofficeMatchingSummary>("/backoffice/matching/summary/", undefined, { token });
}

export async function getBackofficeUnmatchedOffers(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeRawOffer[] | { results: BackofficeRawOffer[]; count: number }>(
    "/backoffice/matching/unmatched/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeConflictOffers(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeRawOffer[] | { results: BackofficeRawOffer[]; count: number }>(
    "/backoffice/matching/conflicts/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeMatchingReview(token: string, reviewId: string): Promise<BackofficeRawOffer> {
  return getJson<BackofficeRawOffer>(`/backoffice/matching/review/${reviewId}/`, undefined, { token });
}

export async function getBackofficeMatchingCandidates(token: string, reviewId: string) {
  return getJson<{ count: number; results: BackofficeMatchingCandidateProduct[] }>(
    `/backoffice/matching/review/${reviewId}/candidates/`,
    undefined,
    { token },
  );
}

export async function confirmBackofficeMatch(
  token: string,
  payload: { raw_offer_id: string; product_id: string; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/confirm/", payload, undefined, { token });
}

export async function ignoreBackofficeOffer(
  token: string,
  payload: { raw_offer_id: string; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/ignore/", payload, undefined, { token });
}

export async function retryBackofficeMatching(
  token: string,
  payload: { raw_offer_id: string; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/retry/", payload, undefined, { token });
}

export async function bulkAutoMatchBackoffice(
  token: string,
  payload: { raw_offer_ids: string[]; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/bulk-auto-match/", payload, undefined, { token });
}

export async function bulkIgnoreBackoffice(
  token: string,
  payload: { raw_offer_ids: string[]; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/bulk-ignore/", payload, undefined, { token });
}

export async function applyManualMatchesBackoffice(
  token: string,
  payload: { mappings: Array<{ raw_offer_id: string; product_id: string }>; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>(
    "/backoffice/matching/actions/apply-manual-matches/",
    payload,
    undefined,
    { token },
  );
}
