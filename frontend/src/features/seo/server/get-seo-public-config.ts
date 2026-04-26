import { cache } from "react";

import { siteConfig } from "@/shared/config/site";

import type { SeoPublicConfig } from "@/features/seo/types";

async function requestJson<T>(path: string): Promise<T | null> {
  const url = `${siteConfig.apiBaseUrl}${path}`;
  try {
    const response = await fetch(url, {
      method: "GET",
      next: { revalidate: 60 },
      credentials: "omit",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export const getSeoPublicConfig = cache(async (): Promise<SeoPublicConfig | null> => {
  return requestJson<SeoPublicConfig>("/seo/public/config/");
});
