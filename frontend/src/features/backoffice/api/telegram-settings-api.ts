import { getJson, patchJson, postJson } from "@/shared/api/http-client";

import type {
  BackofficeTelegramSettings,
  BackofficeTelegramSettingsPatch,
  BackofficeTelegramTestResponse,
  TelegramBotKind,
} from "@/features/backoffice/types/telegram-settings.types";

export async function getBackofficeTelegramSettings(token: string): Promise<BackofficeTelegramSettings> {
  return getJson<BackofficeTelegramSettings>("/backoffice/telegram/settings/", undefined, { token });
}

export async function patchBackofficeTelegramSettings(
  token: string,
  payload: BackofficeTelegramSettingsPatch,
): Promise<BackofficeTelegramSettings> {
  return patchJson<BackofficeTelegramSettings, BackofficeTelegramSettingsPatch>(
    "/backoffice/telegram/settings/",
    payload,
    undefined,
    { token },
  );
}

export async function postBackofficeTelegramTest(
  token: string,
  payload: { bot: TelegramBotKind; text?: string },
): Promise<BackofficeTelegramTestResponse> {
  return postJson<BackofficeTelegramTestResponse, { bot: TelegramBotKind; text?: string }>(
    "/backoffice/telegram/test/",
    payload,
    undefined,
    { token },
  );
}
