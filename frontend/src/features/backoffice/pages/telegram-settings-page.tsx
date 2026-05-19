"use client";

import { LoaderCircle, MessageSquare, Send, ShieldCheck, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeTelegramSettings,
  patchBackofficeTelegramSettings,
  postBackofficeTelegramTest,
} from "@/features/backoffice/api/telegram-settings-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import type {
  BackofficeTelegramSettings,
  BackofficeTelegramSettingsPatch,
  TelegramBotKind,
} from "@/features/backoffice/types/telegram-settings.types";
import { useAuth } from "@/features/auth/hooks/use-auth";

type BotCardConfig = {
  key: TelegramBotKind;
  titleKey: string;
  icon: typeof ShieldCheck;
  chatIdField: "ops_chat_id" | "support_chat_id" | "system_chat_id";
  tokenField: "ops_bot_token" | "support_bot_token" | "system_bot_token";
  tokenMaskedField: keyof BackofficeTelegramSettings;
  testDefaultTextKey: string;
  eventKeys: Array<{
    field:
      | "ops_notify_order_status"
      | "ops_notify_return_created"
      | "ops_notify_return_status"
      | "ops_notify_waybill_created"
      | "ops_notify_waybill_updated"
      | "ops_notify_waybill_deleted"
      | "support_notify_new_thread"
      | "support_notify_new_message"
      | "system_notify_backup_status"
      | "system_notify_import_status";
    labelKey: string;
  }>;
};

const BOT_CARDS: BotCardConfig[] = [
  {
    key: "ops",
    titleKey: "telegramSettings.bots.ops.title",
    icon: ShieldCheck,
    chatIdField: "ops_chat_id",
    tokenField: "ops_bot_token",
    tokenMaskedField: "ops_bot_token_masked",
    testDefaultTextKey: "telegramSettings.bots.ops.testText",
    eventKeys: [
      { field: "ops_notify_order_status", labelKey: "telegramSettings.bots.ops.events.orderStatus" },
      { field: "ops_notify_return_created", labelKey: "telegramSettings.bots.ops.events.returnCreate" },
      { field: "ops_notify_return_status", labelKey: "telegramSettings.bots.ops.events.returnStatus" },
      { field: "ops_notify_waybill_created", labelKey: "telegramSettings.bots.ops.events.waybillCreate" },
      { field: "ops_notify_waybill_updated", labelKey: "telegramSettings.bots.ops.events.waybillUpdate" },
      { field: "ops_notify_waybill_deleted", labelKey: "telegramSettings.bots.ops.events.waybillDelete" },
    ],
  },
  {
    key: "support",
    titleKey: "telegramSettings.bots.support.title",
    icon: MessageSquare,
    chatIdField: "support_chat_id",
    tokenField: "support_bot_token",
    tokenMaskedField: "support_bot_token_masked",
    testDefaultTextKey: "telegramSettings.bots.support.testText",
    eventKeys: [
      { field: "support_notify_new_thread", labelKey: "telegramSettings.bots.support.events.newThread" },
      { field: "support_notify_new_message", labelKey: "telegramSettings.bots.support.events.newMessage" },
    ],
  },
  {
    key: "system",
    titleKey: "telegramSettings.bots.system.title",
    icon: Wrench,
    chatIdField: "system_chat_id",
    tokenField: "system_bot_token",
    tokenMaskedField: "system_bot_token_masked",
    testDefaultTextKey: "telegramSettings.bots.system.testText",
    eventKeys: [
      { field: "system_notify_backup_status", labelKey: "telegramSettings.bots.system.events.backupStatus" },
      { field: "system_notify_import_status", labelKey: "telegramSettings.bots.system.events.importStatus" },
    ],
  },
];

export function TelegramSettingsPage() {
  const t = useTranslations("backoffice.common");
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [settings, setSettings] = useState<BackofficeTelegramSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string>("");
  const [testingKey, setTestingKey] = useState<string>("");
  const [botTokens, setBotTokens] = useState<Record<TelegramBotKind, string>>({
    ops: "",
    support: "",
    system: "",
  });

  useEffect(() => {
    async function load() {
      if (!token) {
        setIsLoading(false);
        setError(null);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const payload = await getBackofficeTelegramSettings(token);
        setSettings(payload);
      } catch (loadError) {
        setError(showApiError(loadError, t("telegramSettings.messages.loadFailed")));
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [showApiError, t, token]);

  const isEmpty = useMemo(() => !settings, [settings]);

  async function patchSettings(payload: BackofficeTelegramSettingsPatch, successMessage: string, key: string) {
    if (!token || !settings) {
      return;
    }
    setSavingKey(key);
    try {
      const next = await patchBackofficeTelegramSettings(token, payload);
      setSettings(next);
      showSuccess(successMessage);
    } catch (patchError) {
      showApiError(patchError, t("telegramSettings.messages.saveFailed"));
    } finally {
      setSavingKey("");
    }
  }

  async function handleBotSave(config: BotCardConfig) {
    if (!settings) {
      return;
    }
    const payload: BackofficeTelegramSettingsPatch = {
      [config.chatIdField]: String(settings[config.chatIdField] || "").trim(),
    };
    const nextToken = botTokens[config.key].trim();
    if (nextToken) {
      payload[config.tokenField] = nextToken;
    }
    await patchSettings(payload, t("telegramSettings.messages.saved"), `save:${config.key}`);
    setBotTokens((prev) => ({ ...prev, [config.key]: "" }));
  }

  async function handleTest(config: BotCardConfig) {
    if (!token) {
      return;
    }
    setTestingKey(config.key);
    try {
      const payload = await postBackofficeTelegramTest(token, {
        bot: config.key,
        text: t(config.testDefaultTextKey),
      });
      if (payload.ok) {
        showSuccess(t("telegramSettings.messages.testOk"));
      } else {
        showApiError(new Error(payload.message), payload.message || t("telegramSettings.messages.testFailed"));
      }
    } catch (testError) {
      showApiError(testError, t("telegramSettings.messages.testFailed"));
    } finally {
      setTestingKey("");
    }
  }

  return (
    <AsyncState isLoading={isLoading} error={error} empty={isEmpty} emptyLabel={t("telegramSettings.messages.empty")}>
      <section className="grid gap-4">
        <PageHeader title={t("telegramSettings.title")} description={t("telegramSettings.subtitle")} />

        <div className="grid gap-3 xl:grid-cols-3">
          {BOT_CARDS.map((config) => {
            const masked = String(settings?.[config.tokenMaskedField] || "");
            const isSaving = savingKey === `save:${config.key}`;
            const isTesting = testingKey === config.key;
            return (
              <article key={config.key} className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
                  <config.icon size={16} />
                  <span>{t(config.titleKey)}</span>
                </p>

                <div className="grid gap-2">
                  <label className="grid gap-1 text-xs">
                    <span>{t("telegramSettings.fields.botToken")}</span>
                    <input
                      type="password"
                      value={botTokens[config.key]}
                      onChange={(event) => setBotTokens((prev) => ({ ...prev, [config.key]: event.target.value }))}
                      placeholder={masked || "********"}
                      className="h-9 rounded-md border px-2"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    />
                    <span style={{ color: "var(--muted)" }}>
                      {masked ? t("telegramSettings.fields.savedToken", { value: masked }) : t("telegramSettings.fields.noToken")}
                    </span>
                  </label>

                  <label className="grid gap-1 text-xs">
                    <span>{t("telegramSettings.fields.chatId")}</span>
                    <input
                      value={String(settings?.[config.chatIdField] || "")}
                      onChange={(event) => {
                        setSettings((prev) => (prev ? { ...prev, [config.chatIdField]: event.target.value } : prev));
                      }}
                      className="h-9 rounded-md border px-2"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    />
                  </label>

                  {config.eventKeys.map((eventConfig) => (
                    <label key={String(eventConfig.field)} className="flex cursor-pointer items-center justify-between rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                      <span>{t(eventConfig.labelKey)}</span>
                      <input
                        type="checkbox"
                        checked={Boolean(settings?.[eventConfig.field])}
                        onChange={(event) => {
                          setSettings((prev) => (prev ? { ...prev, [eventConfig.field]: event.target.checked } : prev));
                        }}
                      />
                    </label>
                  ))}

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold disabled:opacity-60"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        void handleBotSave(config);
                      }}
                      disabled={isSaving}
                    >
                      {isSaving ? <LoaderCircle size={14} className="animate-spin" /> : <Send size={14} />}
                      <span>{t("telegramSettings.actions.save")}</span>
                    </button>

                    <button
                      type="button"
                      className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold disabled:opacity-60"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        void handleTest(config);
                      }}
                      disabled={isTesting}
                    >
                      {isTesting ? <LoaderCircle size={14} className="animate-spin" /> : <MessageSquare size={14} />}
                      <span>{t("telegramSettings.actions.test")}</span>
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </AsyncState>
  );
}
