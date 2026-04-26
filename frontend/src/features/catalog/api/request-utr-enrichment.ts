import { postJson } from "@/shared/api/http-client";

export type UtrEnrichmentStatus = {
  product_id: string;
  status: string;
  utr_detail_id: string;
  primary_image: string;
  characteristics_count: number;
  queued: boolean;
};

type UtrEnrichmentResponse = {
  results: UtrEnrichmentStatus[];
};

export async function requestUtrProductEnrichment(productIds: string[], enqueue = true): Promise<UtrEnrichmentStatus[]> {
  if (productIds.length === 0) {
    return [];
  }

  const response = await postJson<UtrEnrichmentResponse, { product_ids: string[]; enqueue: boolean }>(
    "/catalog/products/utr-enrichment/",
    {
      product_ids: productIds,
      enqueue,
    },
  );
  return response.results;
}
