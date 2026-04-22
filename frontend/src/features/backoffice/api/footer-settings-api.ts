import { getJson, patchJson } from "@/shared/api/http-client";

import type { BackofficeFooterSettings } from "@/features/backoffice/types/footer-settings.types";

export async function getBackofficeFooterSettings(token: string): Promise<BackofficeFooterSettings> {
  return getJson<BackofficeFooterSettings>("/backoffice/settings/footer/", undefined, { token });
}

export async function updateBackofficeFooterSettings(
  token: string,
  payload: Partial<BackofficeFooterSettings>,
): Promise<BackofficeFooterSettings> {
  return patchJson<BackofficeFooterSettings, Partial<BackofficeFooterSettings>>(
    "/backoffice/settings/footer/",
    payload,
    undefined,
    { token },
  );
}
