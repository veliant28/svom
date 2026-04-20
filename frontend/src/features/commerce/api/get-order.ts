import { getJson } from "@/shared/api/http-client";

import type { Order } from "@/features/commerce/types";

export async function getOrder(token: string, orderId: string): Promise<Order> {
  return getJson<Order>(`/commerce/orders/${orderId}/`, undefined, { token });
}
