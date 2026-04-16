import { getJson } from "@/shared/api/http-client";

import type { HeroSlide } from "../types";

export async function getHeroSlides(locale: string): Promise<HeroSlide[]> {
  return getJson<HeroSlide[]>("/marketing/hero-slides/", { lang: locale });
}
