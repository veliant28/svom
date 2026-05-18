import { getJson, patchJson, postJson } from "@/shared/api/http-client";

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

export type AutoDbRemotePatchPayload = Partial<{
  remote_host: string;
  remote_port: number;
  remote_database: string;
  remote_user: string;
  remote_password: string;
  image_base_url: string;
}>;

export async function patchBackofficeIntegrationCenterAutoDbRemote(
  token: string,
  payload: AutoDbRemotePatchPayload,
): Promise<BackofficeIntegrationCenterResponse> {
  return patchJson<
    BackofficeIntegrationCenterResponse,
    { action: "autodb_remote" } & AutoDbRemotePatchPayload
  >(
    "/backoffice/integrations-center/",
    { action: "autodb_remote", ...payload },
    undefined,
    { token },
  );
}

export type AutoDbRemoteConnectionTestResponse = {
  ok: boolean;
  message: string;
};

export async function postBackofficeIntegrationCenterAutoDbRemoteTestConnection(
  token: string,
): Promise<AutoDbRemoteConnectionTestResponse> {
  return postJson<AutoDbRemoteConnectionTestResponse, Record<string, never>>(
    "/backoffice/integrations-center/autodb-remote/test-connection/",
    {},
    undefined,
    { token },
  );
}
