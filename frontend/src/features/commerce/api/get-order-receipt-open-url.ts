import { getJson } from "@/shared/api/http-client";

export async function getOrderReceiptOpenUrl(token: string, orderId: string): Promise<{ url: string }> {
  return getJson<{ url: string }>(`/commerce/account/orders/${orderId}/receipt/open/`, { mode: "json" }, { token });
}
