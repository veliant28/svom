import { getJson } from "@/shared/api/http-client";

import type { PromoBanner } from "../types";

export async function getPromoBanners(locale: string): Promise<PromoBanner[]> {
  return getJson<PromoBanner[]>("/marketing/promo-banners/", { lang: locale });
}
