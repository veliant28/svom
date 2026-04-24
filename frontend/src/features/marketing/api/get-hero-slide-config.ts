import { getJson } from "@/shared/api/http-client";

import type { HeroSlideConfig } from "@/features/marketing/types";

export async function getHeroSlideConfig(locale: string): Promise<HeroSlideConfig> {
  return getJson<HeroSlideConfig>("/marketing/hero-slides/config/", { lang: locale });
}
