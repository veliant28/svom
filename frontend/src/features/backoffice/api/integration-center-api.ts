import { getJson, patchJson } from "@/shared/api/http-client";

import type {
  BackofficeIntegrationCenterResponse,
  IntegrationTranslatorProvider,
  IntegrationCenterToggleKey,
} from "@/features/backoffice/types/integration-center.types";

export async function getBackofficeIntegrationCenterState(token: string): Promise<BackofficeIntegrationCenterResponse> {
  return getJson<BackofficeIntegrationCenterResponse>("/backoffice/integrations-center/", undefined, { token });
}

export async function patchBackofficeIntegrationCenterToggle(
  token: string,
  key: IntegrationCenterToggleKey,
  enabled: boolean,
): Promise<BackofficeIntegrationCenterResponse> {
  return patchJson<BackofficeIntegrationCenterResponse, { action: "toggle"; key: IntegrationCenterToggleKey; enabled: boolean }>(
    "/backoffice/integrations-center/",
    { action: "toggle", key, enabled },
    undefined,
    { token },
  );
}

export async function patchBackofficeIntegrationCenterTranslator(
  token: string,
  payload: Partial<{ provider: IntegrationTranslatorProvider; google_api_key: string }>,
): Promise<BackofficeIntegrationCenterResponse> {
  return patchJson<
    BackofficeIntegrationCenterResponse,
    { action: "translator"; provider?: IntegrationTranslatorProvider; google_api_key?: string }
  >(
    "/backoffice/integrations-center/",
    { action: "translator", ...payload },
    undefined,
    { token },
  );
}
