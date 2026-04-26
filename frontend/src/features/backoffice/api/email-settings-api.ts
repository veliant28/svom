import { getJson, patchJson, postJson } from "@/shared/api/http-client";

import type {
  BackofficeEmailSettings,
  BackofficeEmailSettingsPayload,
  BackofficeEmailTestResult,
} from "@/features/backoffice/types/email-settings.types";

export async function getBackofficeEmailSettings(token: string): Promise<BackofficeEmailSettings> {
  return getJson<BackofficeEmailSettings>("/backoffice/settings/email/", undefined, { token });
}

export async function updateBackofficeEmailSettings(
  token: string,
  payload: BackofficeEmailSettingsPayload,
): Promise<BackofficeEmailSettings> {
  return patchJson<BackofficeEmailSettings, Record<string, unknown>>(
    "/backoffice/settings/email/",
    payload,
    undefined,
    { token },
  );
}

export async function testBackofficeEmailSettings(token: string, recipient: string): Promise<BackofficeEmailTestResult> {
  return postJson<BackofficeEmailTestResult, { recipient: string }>(
    "/backoffice/settings/email/test/",
    { recipient },
    undefined,
    { token },
  );
}
