"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { CheckCircle2, CircleAlert, Clock3, KeyRound, Plug, RefreshCw, Timer, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  checkBackofficeSupplierConnection,
  getBackofficeImportSchedules,
  obtainBackofficeSupplierToken,
  refreshBackofficeSupplierToken,
  updateBackofficeImportSchedule,
  updateBackofficeSupplierSettings,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import {
  SupplierCodeSwitcher,
  SupplierWorkflowTopActions,
} from "@/features/backoffice/components/suppliers/supplier-workspace-header-controls";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useSupplierWorkspaceScope } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import { useTokenCountdown } from "@/features/backoffice/hooks/use-token-countdown";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import { normalizeStatusKey } from "@/features/backoffice/lib/status";
import type { BackofficeImportSource } from "@/features/backoffice/types/backoffice";

function maskedTokenView(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const compact = value.replace(/\s+/g, "").trim();
  if (!compact) {
    return "-";
  }

  if (compact.includes("...")) {
    return compact.replace("...", ".".repeat(15));
  }

  if (compact.length <= 24) {
    return compact;
  }

  const start = compact.slice(0, 10);
  const end = compact.slice(-8);
  return `${start}${".".repeat(15)}${end}`;
}

function tokenCountdownTone(secondsLeft: number | null, warningThresholdSeconds = 15 * 60): "success" | "warning" | "error" | "info" {
  if (secondsLeft === null) {
    return "info";
  }
  if (secondsLeft <= 0) {
    return "error";
  }
  if (secondsLeft <= warningThresholdSeconds) {
    return "warning";
  }
  return "success";
}

function toneIcon(tone: "success" | "warning" | "error" | "info"): LucideIcon {
  if (tone === "success") {
    return CheckCircle2;
  }
  if (tone === "warning") {
    return CircleAlert;
  }
  if (tone === "error") {
    return XCircle;
  }
  return Plug;
}

function toneStatusKey(tone: "success" | "warning" | "error" | "info"): string {
  if (tone === "success") {
    return "active";
  }
  if (tone === "warning") {
    return "attention";
  }
  if (tone === "error") {
    return "expired";
  }
  return "unknown";
}

export function SuppliersPage() {
  const t = useTranslations("backoffice.suppliers");
  const tAuth = useTranslations("backoffice.auth");
  const tCommon = useTranslations("backoffice.common");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const tErrors = useTranslations("backoffice.errors");
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const {
    activeCode,
    setActiveCode,
    hrefFor,
    token,
    suppliers,
    workspace,
    suppliersLoading,
    workspaceLoading,
    suppliersError,
    workspaceError,
    refreshWorkspaceScope,
  } = useSupplierWorkspaceScope();

  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [fingerprint, setFingerprint] = useState("svom-backoffice");
  const [isEnabled, setIsEnabled] = useState(true);

  useEffect(() => {
    if (!workspace) {
      return;
    }
    setLogin(workspace.connection.login ?? "");
    setIsEnabled(workspace.supplier.is_enabled);
  }, [workspace]);

  const runAction = useCallback(
    async <T,>(
      action: () => Promise<T>,
      options: {
        successMessage: string;
        errorFallback?: string;
      },
    ) => {
      try {
        await action();
        showSuccess(options.successMessage);
        await refreshWorkspaceScope();
      } catch (error: unknown) {
        showApiError(error, options.errorFallback ?? tErrors("actions.failed"));
      }
    },
    [refreshWorkspaceScope, showApiError, showSuccess, tErrors],
  );

  const schedulesQuery = useCallback((apiToken: string) => getBackofficeImportSchedules(apiToken), []);
  const {
    data: schedulesData,
    isLoading: schedulesLoading,
    error: schedulesError,
    refetch: refetchSchedules,
  } = useBackofficeQuery<{ count: number; results: BackofficeImportSource[] }>(schedulesQuery, []);

  const supplierScheduleRows = useMemo(
    () => (schedulesData?.results ?? []).filter((item) => item.supplier_code === activeCode),
    [activeCode, schedulesData],
  );

  const toggleAutoImport = useCallback(
    async (item: BackofficeImportSource) => {
      if (!token) {
        return;
      }
      try {
        await updateBackofficeImportSchedule(token, item.id, {
          is_auto_import_enabled: !item.is_auto_import_enabled,
        });
        showSuccess(tCommon("importSchedules.messages.scheduleUpdated", { source: item.code }));
        await refetchSchedules();
      } catch (error: unknown) {
        showApiError(error, tCommon("importSchedules.messages.actionFailed"));
      }
    },
    [refetchSchedules, showApiError, showSuccess, tCommon, token],
  );

  const saveDefaultCron = useCallback(
    async (item: BackofficeImportSource) => {
      if (!token) {
        return;
      }
      try {
        await updateBackofficeImportSchedule(token, item.id, {
          schedule_cron: item.schedule_cron || "*/30 * * * *",
          schedule_timezone: item.schedule_timezone || "Europe/Kyiv",
          auto_reprice_after_import: item.auto_reprice_after_import,
          auto_reindex_after_import: item.auto_reindex_after_import,
        });
        showSuccess(tCommon("importSchedules.messages.scheduleSaved", { source: item.code }));
        await refetchSchedules();
      } catch (error: unknown) {
        showApiError(error, tCommon("importSchedules.messages.actionFailed"));
      }
    },
    [refetchSchedules, showApiError, showSuccess, tCommon, token],
  );

  const handleSaveSettings = useCallback(async () => {
    if (!token) {
      return;
    }

    await runAction(
      () =>
        updateBackofficeSupplierSettings(token, activeCode, {
          login,
          password: password || undefined,
          browser_fingerprint: fingerprint || undefined,
          is_enabled: isEnabled,
        }),
      {
        successMessage: tAuth("messages.settingsSaved"),
        errorFallback: tAuth("messages.settingsSaveFailed"),
      },
    );

    setPassword("");
  }, [activeCode, fingerprint, isEnabled, login, password, runAction, tAuth, token]);

  const accessSecondsLeft = useTokenCountdown(workspace?.connection.access_token_expires_at);

  const formatCountdown = useCallback(
    (secondsLeft: number | null) => {
      if (secondsLeft === null) {
        return tAuth("status.countdownUnavailable");
      }
      if (secondsLeft <= 0) {
        return tAuth("status.countdownExpired");
      }
      if (secondsLeft < 60) {
        return tAuth("status.countdownLessThanMinute");
      }
      if (secondsLeft < 3600) {
        return tAuth("status.countdownMinutes", { minutes: Math.floor(secondsLeft / 60) });
      }
      if (secondsLeft < 86400) {
        const hours = Math.floor(secondsLeft / 3600);
        const minutes = Math.floor((secondsLeft % 3600) / 60);
        return tAuth("status.countdownHoursMinutes", { hours, minutes });
      }
      const days = Math.floor(secondsLeft / 86400);
      const hours = Math.floor((secondsLeft % 86400) / 3600);
      return tAuth("status.countdownDaysHours", { days, hours });
    },
    [tAuth],
  );

  const connectionLabel = useMemo(() => {
    if (!workspace?.connection.status) {
      return tCommon("statuses.unknown");
    }
    const key = normalizeStatusKey(workspace.connection.status);
    try {
      return tCommon(`statuses.${key}`);
    } catch {
      return tCommon("statuses.unknown");
    }
  }, [tCommon, workspace?.connection.status]);

  const accessTone = tokenCountdownTone(accessSecondsLeft);
  const tokenStateLabel = useMemo(() => {
    const key = toneStatusKey(accessTone);
    try {
      return tCommon(`statuses.${key}`);
    } catch {
      return tCommon("statuses.unknown");
    }
  }, [accessTone, tCommon]);

  const topActions = useMemo(
    () => (
      <SupplierWorkflowTopActions
        activeCode={activeCode}
        currentView="workspace"
        settingsHref={hrefFor("/backoffice/suppliers")}
        importHref={hrefFor("/backoffice/suppliers/import")}
        importRunsHref={hrefFor("/backoffice/suppliers/import-runs")}
        importErrorsHref={hrefFor("/backoffice/suppliers/import-errors")}
        importQualityHref={hrefFor("/backoffice/suppliers/import-quality")}
        productsHref={hrefFor("/backoffice/suppliers/products")}
        brandsHref={hrefFor("/backoffice/suppliers/brands", "utr")}
        onRefresh={() => {
          void refreshWorkspaceScope();
        }}
        settingsLabel={t("actions.settings")}
        importLabel={t("actions.import")}
        importRunsLabel={t("actions.importRuns")}
        importErrorsLabel={t("actions.importErrors")}
        importQualityLabel={t("actions.importQuality")}
        productsLabel={t("actions.products")}
        brandsLabel={t("actions.brands")}
        refreshLabel={t("actions.refreshAll")}
      />
    ),
    [activeCode, hrefFor, refreshWorkspaceScope, t],
  );

  const switcher = useMemo(
    () => (
      <SupplierCodeSwitcher
        activeCode={activeCode}
        onChange={setActiveCode}
        utrLabel={tUtr("label")}
        gplLabel={tGpl("label")}
        ariaLabel={t("title")}
      />
    ),
    [activeCode, setActiveCode, t, tGpl, tUtr],
  );

  return (
    <section>
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        switcher={switcher}
        actions={topActions}
      />

      <AsyncState
        isLoading={suppliersLoading || workspaceLoading}
        error={suppliersError || workspaceError}
        empty={!workspace}
        emptyLabel={t("states.emptyWorkspace")}
      >
        {workspace ? (
          <div className="grid gap-4">
            <section className="grid gap-4 lg:grid-cols-2">
              <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{tAuth("cards.authorization")}</h2>
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{tAuth("subtitle")}</p>

                <div className="mt-3 max-w-xl space-y-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label className="grid gap-1">
                      <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>
                        {tAuth("fields.login")}
                      </span>
                      <input
                        value={login}
                        onChange={(event) => setLogin(event.target.value)}
                        className="h-10 rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      />
                    </label>
                    <label className="grid gap-1">
                      <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>
                        {tAuth("fields.password")}
                      </span>
                      <input
                        type="password"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        className="h-10 rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      />
                    </label>
                    {activeCode === "utr" ? (
                      <label className="grid gap-1 sm:col-span-2">
                        <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>
                          {tAuth("fields.fingerprint")}
                        </span>
                        <input
                          value={fingerprint}
                          onChange={(event) => setFingerprint(event.target.value)}
                          className="h-10 rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        />
                      </label>
                    ) : null}
                  </div>

                  <label className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      onChange={(event) => setIsEnabled(event.target.checked)}
                    />
                    {tAuth("fields.enabled")}
                  </label>

                  <div className="grid gap-2 sm:grid-cols-2">
                    <button
                      type="button"
                      className="h-10 rounded-md border px-3 text-sm font-semibold"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        void handleSaveSettings();
                      }}
                    >
                      {tAuth("actions.saveSettings")}
                    </button>
                    <button
                      type="button"
                      className="h-10 rounded-md border px-3 text-sm font-semibold"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        if (!token) {
                          return;
                        }
                        void runAction(
                          () => obtainBackofficeSupplierToken(token, activeCode),
                          {
                            successMessage: tAuth("messages.tokenObtained"),
                            errorFallback: tAuth("messages.tokenObtainFailed"),
                          },
                        );
                      }}
                    >
                      {tAuth("actions.obtainToken")}
                    </button>
                    <button
                      type="button"
                      className="h-10 rounded-md border px-3 text-sm font-semibold"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        if (!token) {
                          return;
                        }
                        void runAction(
                          () => refreshBackofficeSupplierToken(token, activeCode),
                          {
                            successMessage: tAuth("messages.tokenRefreshed"),
                            errorFallback: tAuth("messages.tokenRefreshFailed"),
                          },
                        );
                      }}
                    >
                      {tAuth("actions.refreshToken")}
                    </button>
                    <button
                      type="button"
                      className="h-10 rounded-md border px-3 text-sm font-semibold"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        if (!token) {
                          return;
                        }
                        void runAction(
                          () => checkBackofficeSupplierConnection(token, activeCode),
                          {
                            successMessage: tAuth("messages.connectionChecked"),
                            errorFallback: tAuth("messages.connectionCheckFailed"),
                          },
                        );
                      }}
                    >
                      {tAuth("actions.checkConnection")}
                    </button>
                  </div>
                </div>
              </article>

              <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold">{tAuth("cards.status")}</h2>
                    <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{tAuth("status.subtitle")}</p>
                  </div>
                  <BackofficeStatusChip tone={accessTone} icon={toneIcon(accessTone)}>
                    {tokenStateLabel}
                  </BackofficeStatusChip>
                </div>

                <div className="mt-3 overflow-hidden rounded-xl border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <div className="grid gap-1.5 px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)] sm:items-center">
                    <p className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--muted)" }}>
                      <Plug size={18} />
                      {tAuth("status.connection")}
                    </p>
                    <p className="text-sm font-semibold">{connectionLabel}</p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
                    <p className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--muted)" }}>
                      <Clock3 size={18} />
                      {tAuth("status.accessExpires")}
                    </p>
                    <p className="text-sm font-semibold">{formatBackofficeDate(workspace.connection.access_token_expires_at)}</p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
                    <p className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--muted)" }}>
                      <Clock3 size={18} />
                      {tAuth("status.refreshExpires")}
                    </p>
                    <p className="text-sm font-semibold">{formatBackofficeDate(workspace.connection.refresh_token_expires_at)}</p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
                    <p className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--muted)" }}>
                      <RefreshCw size={18} />
                      {tAuth("status.lastRefresh")}
                    </p>
                    <p className="text-sm font-semibold">{formatBackofficeDate(workspace.connection.last_token_refresh_at)}</p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)]" style={{ borderTopColor: "var(--border)" }}>
                    <p className="inline-flex items-center gap-2 text-xs font-semibold sm:mt-0.5" style={{ color: "var(--muted)" }}>
                      <KeyRound size={18} />
                      {tAuth("status.accessMasked")}
                    </p>
                    <p className="break-all font-mono text-sm font-semibold leading-5">{maskedTokenView(workspace.connection.access_token_masked)}</p>
                  </div>
                  <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)]" style={{ borderTopColor: "var(--border)" }}>
                    <p className="inline-flex items-center gap-2 text-xs font-semibold sm:mt-0.5" style={{ color: "var(--muted)" }}>
                      <KeyRound size={18} />
                      {tAuth("status.refreshMasked")}
                    </p>
                    <p className="break-all font-mono text-sm font-semibold leading-5">{maskedTokenView(workspace.connection.refresh_token_masked)}</p>
                  </div>
                </div>

                <div className="mt-2.5 flex justify-end">
                  <BackofficeStatusChip tone={accessTone} icon={Timer} palette="countdown">
                    {formatCountdown(accessSecondsLeft)}
                  </BackofficeStatusChip>
                </div>
              </article>
            </section>

            <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <h2 className="text-sm font-semibold">{tCommon("importSchedules.title")}</h2>
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                {tCommon("importSchedules.subtitle")}
              </p>

              <div className="mt-3">
                <AsyncState
                  isLoading={schedulesLoading}
                  error={schedulesError}
                  empty={!supplierScheduleRows.length}
                  emptyLabel={tCommon("importSchedules.states.empty")}
                >
                  <BackofficeTable
                    emptyLabel={tCommon("importSchedules.states.empty")}
                    rows={supplierScheduleRows}
                    columns={[
                      {
                        key: "source",
                        label: tCommon("importSchedules.table.columns.source"),
                        render: (item) => (
                          <div>
                            <p className="font-semibold">{item.name}</p>
                            <p className="text-xs" style={{ color: "var(--muted)" }}>
                              {item.code} / {item.supplier_code}
                            </p>
                          </div>
                        ),
                      },
                      {
                        key: "enabled",
                        label: tCommon("importSchedules.table.columns.enabled"),
                        render: (item) => <StatusChip status={item.is_auto_import_enabled ? "enabled" : "disabled"} />,
                      },
                      {
                        key: "cron",
                        label: tCommon("importSchedules.table.columns.cron"),
                        render: (item) => (
                          <div>
                            <p>{item.schedule_cron || "-"}</p>
                            <p className="text-xs" style={{ color: "var(--muted)" }}>
                              {item.schedule_timezone}
                            </p>
                          </div>
                        ),
                      },
                      {
                        key: "nextRun",
                        label: tCommon("importSchedules.table.columns.nextRun"),
                        render: (item) => item.next_run || "-",
                      },
                      {
                        key: "lastResult",
                        label: tCommon("importSchedules.table.columns.lastResult"),
                        render: (item) =>
                          item.last_run ? (
                            <div>
                              <StatusChip status={item.last_run.status} />
                              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                                {tCommon("importSchedules.table.lastRunSummary", {
                                  rows: item.last_run.processed_rows,
                                  errors: item.last_run.errors_count,
                                })}
                              </p>
                            </div>
                          ) : (
                            "-"
                          ),
                      },
                      {
                        key: "actions",
                        label: tCommon("importSchedules.table.columns.actions"),
                        render: (item) => (
                          <div className="flex flex-wrap gap-1">
                            <button
                              type="button"
                              className="h-8 rounded-md border px-2 text-xs"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                              onClick={() => {
                                void toggleAutoImport(item);
                              }}
                            >
                              {item.is_auto_import_enabled
                                ? tCommon("importSchedules.actions.disable")
                                : tCommon("importSchedules.actions.enable")}
                            </button>
                            <button
                              type="button"
                              className="h-8 rounded-md border px-2 text-xs"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                              onClick={() => {
                                void saveDefaultCron(item);
                              }}
                            >
                              {tCommon("importSchedules.actions.saveDefaults")}
                            </button>
                          </div>
                        ),
                      },
                    ]}
                  />
                </AsyncState>
              </div>
            </article>

            <p className="text-xs" style={{ color: "var(--muted)" }}>
              {t("footer.availableSuppliers", { count: suppliers?.length ?? 0 })}
            </p>
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
