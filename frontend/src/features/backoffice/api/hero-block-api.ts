import { ApiRequestError, deleteJson, getJson, patchJson } from "@/shared/api/http-client";
import { siteConfig } from "@/shared/config/site";

import type {
  BackofficeHeroBlockSettings,
  BackofficeHeroSlide,
} from "@/features/backoffice/types/hero-block.types";

type BackofficeHeroSlideWritePayload = {
  title_uk?: string;
  title_ru?: string;
  title_en?: string;
  subtitle_uk?: string;
  subtitle_ru?: string;
  subtitle_en?: string;
  cta_url?: string;
  sort_order?: number;
  is_active?: boolean;
  desktop_image?: File;
  mobile_image?: File;
};

export async function getBackofficeHeroBlockSettings(token: string): Promise<BackofficeHeroBlockSettings> {
  return getJson<BackofficeHeroBlockSettings>("/backoffice/settings/hero-block/", undefined, { token });
}

export async function updateBackofficeHeroBlockSettings(
  token: string,
  payload: Partial<BackofficeHeroBlockSettings>,
): Promise<BackofficeHeroBlockSettings> {
  return patchJson<BackofficeHeroBlockSettings, Partial<BackofficeHeroBlockSettings>>(
    "/backoffice/settings/hero-block/",
    payload,
    undefined,
    { token },
  );
}

export async function listBackofficeHeroSlides(token: string): Promise<{ count: number; results: BackofficeHeroSlide[] }> {
  return getJson<{ count: number; results: BackofficeHeroSlide[] }>(
    "/backoffice/settings/hero-block/items/",
    undefined,
    { token },
  );
}

export async function createBackofficeHeroSlide(
  token: string,
  payload: BackofficeHeroSlideWritePayload,
): Promise<BackofficeHeroSlide> {
  return requestBackofficeHeroBlockFormData<BackofficeHeroSlide>(
    "POST",
    "/backoffice/settings/hero-block/items/",
    token,
    payload,
  );
}

export async function updateBackofficeHeroSlide(
  token: string,
  id: string,
  payload: BackofficeHeroSlideWritePayload,
): Promise<BackofficeHeroSlide> {
  return requestBackofficeHeroBlockFormData<BackofficeHeroSlide>(
    "PATCH",
    `/backoffice/settings/hero-block/items/${id}/`,
    token,
    payload,
  );
}

export async function deleteBackofficeHeroSlide(token: string, id: string): Promise<void> {
  await deleteJson(`/backoffice/settings/hero-block/items/${id}/`, undefined, { token });
}

async function requestBackofficeHeroBlockFormData<T>(
  method: "POST" | "PATCH",
  path: string,
  token: string,
  payload: BackofficeHeroSlideWritePayload,
): Promise<T> {
  const requestUrl = `${siteConfig.apiBaseUrl}${path}`;
  const formData = new FormData();

  appendIfPresent(formData, "title_uk", payload.title_uk);
  appendIfPresent(formData, "title_ru", payload.title_ru);
  appendIfPresent(formData, "title_en", payload.title_en);
  appendIfPresent(formData, "subtitle_uk", payload.subtitle_uk);
  appendIfPresent(formData, "subtitle_ru", payload.subtitle_ru);
  appendIfPresent(formData, "subtitle_en", payload.subtitle_en);
  appendIfPresent(formData, "cta_url", payload.cta_url);
  appendIfPresent(formData, "sort_order", payload.sort_order);
  appendIfPresent(formData, "is_active", payload.is_active);
  if (payload.desktop_image instanceof File) {
    formData.append("desktop_image", payload.desktop_image);
  }
  if (payload.mobile_image instanceof File) {
    formData.append("mobile_image", payload.mobile_image);
  }

  let response: Response;
  try {
    response = await fetch(requestUrl, {
      method,
      headers: {
        Authorization: `Token ${token}`,
      },
      body: formData,
      cache: "no-store",
      credentials: "omit",
    });
  } catch {
    throw new ApiRequestError({
      message: "Network error while sending request.",
      url: requestUrl,
      isNetworkError: true,
    });
  }

  if (!response.ok) {
    let payloadJson: Record<string, unknown> | undefined;
    try {
      const rawErrorBody = await response.text();
      if (rawErrorBody) {
        payloadJson = JSON.parse(rawErrorBody) as Record<string, unknown>;
      }
    } catch {
      payloadJson = undefined;
    }

    throw new ApiRequestError({
      message: String(payloadJson?.detail || payloadJson?.message || `API request failed with ${response.status}`),
      status: response.status,
      payload: payloadJson,
      url: requestUrl,
    });
  }

  return (await response.json()) as T;
}

function appendIfPresent(formData: FormData, key: string, value: unknown): void {
  if (value === undefined) {
    return;
  }
  if (value === null) {
    formData.append(key, "");
    return;
  }
  if (typeof value === "boolean") {
    formData.append(key, value ? "true" : "false");
    return;
  }
  formData.append(key, String(value));
}
