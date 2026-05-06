import { ApiRequestError, deleteJson, getJson, patchJson } from "@/shared/api/http-client";
import { siteConfig } from "@/shared/config/site";

import type {
  BackofficePromoBanner,
  BackofficePromoBannerSettings,
} from "@/features/backoffice/types/promo-banners.types";

type BackofficePromoBannerWritePayload = {
  title?: string;
  description?: string;
  target_url?: string;
  sort_order?: number;
  is_active?: boolean;
  starts_at?: string | null;
  ends_at?: string | null;
  image?: File;
};

export async function getBackofficePromoBannerSettings(token: string): Promise<BackofficePromoBannerSettings> {
  return getJson<BackofficePromoBannerSettings>("/backoffice/settings/promo-banners/", undefined, { token });
}

export async function updateBackofficePromoBannerSettings(
  token: string,
  payload: Partial<BackofficePromoBannerSettings>,
): Promise<BackofficePromoBannerSettings> {
  return patchJson<BackofficePromoBannerSettings, Partial<BackofficePromoBannerSettings>>(
    "/backoffice/settings/promo-banners/",
    payload,
    undefined,
    { token },
  );
}

export async function listBackofficePromoBanners(token: string): Promise<{ count: number; results: BackofficePromoBanner[] }> {
  const payload = await getJson<{ count: number; results: BackofficePromoBanner[] }>(
    "/backoffice/settings/promo-banners/items/",
    undefined,
    { token },
  );
  return {
    ...payload,
    results: (payload.results || []).map(normalizeBackofficePromoBanner),
  };
}

export async function createBackofficePromoBanner(
  token: string,
  payload: BackofficePromoBannerWritePayload,
): Promise<BackofficePromoBanner> {
  const created = await requestBackofficePromoBannerFormData<BackofficePromoBanner>(
    "POST",
    "/backoffice/settings/promo-banners/items/",
    token,
    payload,
  );
  return normalizeBackofficePromoBanner(created);
}

export async function updateBackofficePromoBanner(
  token: string,
  id: string,
  payload: BackofficePromoBannerWritePayload,
): Promise<BackofficePromoBanner> {
  const updated = await requestBackofficePromoBannerFormData<BackofficePromoBanner>(
    "PATCH",
    `/backoffice/settings/promo-banners/items/${id}/`,
    token,
    payload,
  );
  return normalizeBackofficePromoBanner(updated);
}

export async function deleteBackofficePromoBanner(token: string, id: string): Promise<void> {
  await deleteJson(`/backoffice/settings/promo-banners/items/${id}/`, undefined, { token });
}

async function requestBackofficePromoBannerFormData<T>(
  method: "POST" | "PATCH",
  path: string,
  token: string,
  payload: BackofficePromoBannerWritePayload,
): Promise<T> {
  const requestUrl = `${siteConfig.apiBaseUrl}${path}`;
  const formData = new FormData();

  appendIfPresent(formData, "title", payload.title);
  appendIfPresent(formData, "description", payload.description);
  appendIfPresent(formData, "target_url", payload.target_url);
  appendIfPresent(formData, "sort_order", payload.sort_order);
  appendIfPresent(formData, "is_active", payload.is_active);
  appendIfPresent(formData, "starts_at", payload.starts_at);
  appendIfPresent(formData, "ends_at", payload.ends_at);
  if (payload.image instanceof File) {
    formData.append("image", payload.image);
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
    let rawErrorBody: string | undefined;
    try {
      rawErrorBody = await response.text();
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

function normalizeBackofficePromoBanner(banner: BackofficePromoBanner): BackofficePromoBanner {
  return {
    ...banner,
    image_url: resolveRuntimeMediaUrl(banner.image_url),
  };
}

function resolveRuntimeMediaUrl(value: string): string {
  const rawValue = String(value || "").trim();
  if (!rawValue) {
    return "";
  }

  const mediaPath = extractMediaPath(rawValue);
  if (!mediaPath) {
    return rawValue;
  }
  return mediaPath;
}

function extractMediaPath(value: string): string | null {
  if (value.startsWith("/media/")) {
    return value;
  }

  try {
    const parsed = new URL(value);
    if (parsed.pathname.startsWith("/media/")) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  } catch {
    return null;
  }
  return null;
}
