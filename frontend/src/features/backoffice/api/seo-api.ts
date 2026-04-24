import { deleteJson, getJson, patchJson, postJson } from "@/shared/api/http-client";

import type {
  BackofficeGoogleSettingsPayload,
  BackofficeSeoDashboard,
  BackofficeSeoListResponse,
  BackofficeSeoMetaOverride,
  BackofficeSeoMetaTemplate,
  BackofficeSeoRobotsPreview,
  BackofficeSeoSettings,
  BackofficeSeoSitemapRebuildResponse,
  SeoEntityType,
  SeoLocale,
} from "@/features/backoffice/api/seo-api.types";

export async function getBackofficeSeoSettings(token: string): Promise<BackofficeSeoSettings> {
  return getJson<BackofficeSeoSettings>("/seo/backoffice/settings/", undefined, { token });
}

export async function updateBackofficeSeoSettings(
  token: string,
  payload: Partial<BackofficeSeoSettings>,
): Promise<BackofficeSeoSettings> {
  return patchJson<BackofficeSeoSettings, Partial<BackofficeSeoSettings>>(
    "/seo/backoffice/settings/",
    payload,
    undefined,
    { token },
  );
}

export async function getBackofficeGoogleSettings(token: string): Promise<BackofficeGoogleSettingsPayload> {
  return getJson<BackofficeGoogleSettingsPayload>("/seo/backoffice/google/", undefined, { token });
}

export async function updateBackofficeGoogleSettings(
  token: string,
  payload: Partial<BackofficeGoogleSettingsPayload["settings"]> & {
    events?: Array<{ id?: string; event_name?: string; is_enabled: boolean }>;
  },
): Promise<BackofficeGoogleSettingsPayload> {
  return patchJson<BackofficeGoogleSettingsPayload, typeof payload>(
    "/seo/backoffice/google/",
    payload,
    undefined,
    { token },
  );
}

export async function getBackofficeSeoTemplates(token: string): Promise<BackofficeSeoListResponse<BackofficeSeoMetaTemplate>> {
  return getJson<BackofficeSeoListResponse<BackofficeSeoMetaTemplate>>("/seo/backoffice/templates/", undefined, { token });
}

export async function createBackofficeSeoTemplate(
  token: string,
  payload: {
    entity_type: SeoEntityType;
    locale: SeoLocale;
    title_template: string;
    description_template: string;
    h1_template: string;
    og_title_template: string;
    og_description_template: string;
    is_active: boolean;
  },
): Promise<BackofficeSeoMetaTemplate> {
  return postJson<BackofficeSeoMetaTemplate, typeof payload>("/seo/backoffice/templates/", payload, undefined, { token });
}

export async function updateBackofficeSeoTemplate(
  token: string,
  id: string,
  payload: Partial<{
    entity_type: SeoEntityType;
    locale: SeoLocale;
    title_template: string;
    description_template: string;
    h1_template: string;
    og_title_template: string;
    og_description_template: string;
    is_active: boolean;
  }>,
): Promise<BackofficeSeoMetaTemplate> {
  return patchJson<BackofficeSeoMetaTemplate, typeof payload>(`/seo/backoffice/templates/${id}/`, payload, undefined, { token });
}

export async function deleteBackofficeSeoTemplate(token: string, id: string): Promise<void> {
  await deleteJson(`/seo/backoffice/templates/${id}/`, undefined, { token });
}

export async function getBackofficeSeoOverrides(token: string): Promise<BackofficeSeoListResponse<BackofficeSeoMetaOverride>> {
  return getJson<BackofficeSeoListResponse<BackofficeSeoMetaOverride>>("/seo/backoffice/overrides/", undefined, { token });
}

export async function createBackofficeSeoOverride(
  token: string,
  payload: {
    path: string;
    locale: SeoLocale;
    meta_title: string;
    meta_description: string;
    h1: string;
    canonical_url: string;
    robots_directive: string;
    og_title: string;
    og_description: string;
    og_image_url: string;
    is_active: boolean;
  },
): Promise<BackofficeSeoMetaOverride> {
  return postJson<BackofficeSeoMetaOverride, typeof payload>("/seo/backoffice/overrides/", payload, undefined, { token });
}

export async function updateBackofficeSeoOverride(
  token: string,
  id: string,
  payload: Partial<{
    path: string;
    locale: SeoLocale;
    meta_title: string;
    meta_description: string;
    h1: string;
    canonical_url: string;
    robots_directive: string;
    og_title: string;
    og_description: string;
    og_image_url: string;
    is_active: boolean;
  }>,
): Promise<BackofficeSeoMetaOverride> {
  return patchJson<BackofficeSeoMetaOverride, typeof payload>(`/seo/backoffice/overrides/${id}/`, payload, undefined, { token });
}

export async function deleteBackofficeSeoOverride(token: string, id: string): Promise<void> {
  await deleteJson(`/seo/backoffice/overrides/${id}/`, undefined, { token });
}

export async function getBackofficeSeoDashboard(token: string): Promise<BackofficeSeoDashboard> {
  return getJson<BackofficeSeoDashboard>("/seo/backoffice/dashboard/", undefined, { token });
}

export async function rebuildBackofficeSitemap(token: string): Promise<BackofficeSeoSitemapRebuildResponse> {
  return postJson<BackofficeSeoSitemapRebuildResponse, Record<string, never>>(
    "/seo/backoffice/sitemap/rebuild/",
    {},
    undefined,
    { token },
  );
}

export async function previewBackofficeRobots(token: string): Promise<BackofficeSeoRobotsPreview> {
  return getJson<BackofficeSeoRobotsPreview>("/seo/backoffice/robots/preview/", undefined, { token });
}
