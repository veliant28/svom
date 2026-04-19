import { getJson } from "@/shared/api/http-client";

import type { Order } from "@/features/commerce/types";

export async function getOrders(token: string): Promise<Order[]> {
  return getJson<Order[]>("/commerce/orders/", undefined, { token });
}
