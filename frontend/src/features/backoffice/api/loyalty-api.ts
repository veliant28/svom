import { getJson, postJson } from "@/shared/api/http-client";

import type {
  BackofficeLoyaltyCustomerOption,
  BackofficeLoyaltyPromo,
  BackofficeLoyaltyStatsResponse,
} from "@/features/backoffice/types/backoffice";

export async function getBackofficeLoyaltyCustomers(token: string, query: string): Promise<{ results: BackofficeLoyaltyCustomerOption[] }> {
  return getJson<{ results: BackofficeLoyaltyCustomerOption[] }>("/backoffice/loyalty/customers/", { query }, { token });
}

export async function issueBackofficeLoyaltyPromo(
  token: string,
  payload: {
    customer_id: number;
    reason: string;
    discount_type: "delivery_fee" | "product_markup";
    discount_percent: number;
    expires_at?: string | null;
    usage_limit?: number;
  },
): Promise<BackofficeLoyaltyPromo> {
  return postJson<BackofficeLoyaltyPromo, typeof payload>("/backoffice/loyalty/issue/", payload, undefined, { token });
}

export async function getBackofficeLoyaltyIssuances(token: string, limit = 25): Promise<BackofficeLoyaltyPromo[]> {
  return getJson<BackofficeLoyaltyPromo[]>("/backoffice/loyalty/issuances/", { limit }, { token });
}

export async function getBackofficeLoyaltyStats(token: string, days = 14): Promise<BackofficeLoyaltyStatsResponse> {
  return getJson<BackofficeLoyaltyStatsResponse>("/backoffice/loyalty/stats/", { days }, { token });
}
