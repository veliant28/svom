import { getJson } from "@/shared/api/http-client";

import type { ProductDetail } from "../types";

export async function getProductDetail(slug: string, locale?: string): Promise<ProductDetail> {
  return getJson<ProductDetail>(`/catalog/products/${slug}/`, locale ? { locale } : undefined);
}
