"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, DatabaseBackup, Minus, Plus, Power, RefreshCw, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  getBackofficeDatabaseBackupSchedule,
  getBackofficeImportRun,
  getBackofficeImportSchedules,
  runBackofficeDatabaseBackup,
  runBackofficeImportSchedule,
  updateBackofficeDatabaseBackupSchedule,
  updateBackofficeImportSchedule,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeDatabaseBackupSchedule, BackofficeImportRun, BackofficeImportSource } from "@/features/backoffice/types/backoffice";
import { useTheme } from "@/shared/components/theme/theme-provider";

type ScheduleDraft = {
  schedule_run_time: string;
  schedule_timezone: string;
  schedule_every_day: boolean;
};

type DatabaseBackupDraft = {
  is_enabled: boolean;
  schedule_run_time: string;
  schedule_timezone: string;
  backup_directory: string;
  retention_count: number;
};

type BackupProfileCode = "postgresql" | "autodb_clone";

type BackupProfile = {
  code: BackupProfileCode;
  defaultTime: string;
  defaultDirectory: string;
};

type ImportScheduleRow =
  | { kind: "backup"; profileCode: BackupProfileCode }
  | { kind: "source"; source: BackofficeImportSource };

const BACKUP_PROFILES: BackupProfile[] = [
  { code: "postgresql", defaultTime: "23:00", defaultDirectory: "Backup" },
  { code: "autodb_clone", defaultTime: "01:00", defaultDirectory: "Backup/autodb-clone" },
];

function buildDraft(item: BackofficeImportSource): ScheduleDraft {
  return {
    schedule_run_time: item.schedule_run_time || "01:00",
    schedule_timezone: item.schedule_timezone || "Europe/Kyiv",
    schedule_every_day: item.schedule_every_day !== false,
  };
}

function buildBackupDraft(item: BackofficeDatabaseBackupSchedule | null, profile: BackupProfile): DatabaseBackupDraft {
  return {
    is_enabled: item?.is_enabled ?? true,
    schedule_run_time: item?.schedule_run_time || profile.defaultTime,
    schedule_timezone: item?.schedule_timezone || "Europe/Kyiv",
    backup_directory: item?.backup_directory || profile.defaultDirectory,
    retention_count: item?.retention_count || 3,
  };
}

function formatBackupSize(value: number): string {
  if (!value) {
    return "-";
  }
  if (value < 1024 * 1024) {
    return `${Math.max(1, Math.round(value / 1024))} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

const ACTIVE_IMPORT_RUN_STATUSES = new Set(["pending", "running"]);

type ImportRunStatusSnapshot = {
  status: string;
  finished_at: string | null;
} | null;

function isActiveImportRunSnapshot(run: ImportRunStatusSnapshot): boolean {
  if (!run?.status || run.finished_at) {
    return false;
  }
  return ACTIVE_IMPORT_RUN_STATUSES.has(run.status.toLowerCase());
}

function hasActiveImportRun(item: BackofficeImportSource): boolean {
  return isActiveImportRunSnapshot(item.last_run);
}

function isRunningStatus(status: string | null | undefined): boolean {
  return String(status || "").trim().toLowerCase() === "running";
}

function ScheduleRunActionButton({
  item,
  token,
  localRunning,
  runLabel,
  runningLabel,
  onRun,
  onRunFinished,
}: {
  item: BackofficeImportSource;
  token: string | null;
  localRunning: boolean;
  runLabel: string;
  runningLabel: string;
  onRun: () => void;
  onRunFinished: () => void;
}) {
  const [polledRun, setPolledRun] = useState<BackofficeImportRun | null>(null);
  const runId = item.last_run?.id || "";
  const currentRun = polledRun && polledRun.id === runId ? polledRun : item.last_run;
  const isBackendRunning = isActiveImportRunSnapshot(currentRun);
  const runLocked = localRunning || isBackendRunning;

  useEffect(() => {
    setPolledRun(null);
  }, [item.last_run?.finished_at, item.last_run?.id, item.last_run?.status]);

  useEffect(() => {
    if (!token || !runId || !isBackendRunning) {
      return undefined;
    }

    let cancelled = false;
    const pollRun = async () => {
      try {
        const nextRun = await getBackofficeImportRun(token, runId);
        if (cancelled) {
          return;
        }
        setPolledRun(nextRun);
        if (!isActiveImportRunSnapshot(nextRun)) {
          onRunFinished();
        }
      } catch {
        // Keep the button locked on transient polling failures; the next tick will retry.
      }
    };

    void pollRun();
    const intervalId = window.setInterval(() => {
      void pollRun();
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [isBackendRunning, onRunFinished, runId, token]);

  return (
    <ActionIconButton
      label={runLocked ? runningLabel : runLabel}
      icon={Check}
      disabled={runLocked}
      onClick={onRun}
    />
  );
}

export function ImportSchedulesPage() {
  const t = useTranslations("backoffice.common");
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const monoActiveBackground = isDark ? "#ffffff" : "#000000";
  const monoActiveText = isDark ? "#111111" : "#ffffff";
  const [q, setQ] = useState("");
  const [drafts, setDrafts] = useState<Record<string, ScheduleDraft>>({});
  const [backupDraftByCode, setBackupDraftByCode] = useState<Partial<Record<BackupProfileCode, DatabaseBackupDraft>>>({});
  const [backupRunningByCode, setBackupRunningByCode] = useState<Partial<Record<BackupProfileCode, boolean>>>({});
  const [runningBySource, setRunningBySource] = useState<Record<string, boolean>>({});
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeImportSchedules(token, {
        q,
      }),
    [q],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeImportSource[] }>(queryFn, [q]);
  const backupMainQueryFn = useCallback((authToken: string) => getBackofficeDatabaseBackupSchedule(authToken, "postgresql"), []);
  const backupCloneQueryFn = useCallback((authToken: string) => getBackofficeDatabaseBackupSchedule(authToken, "autodb_clone"), []);
  const {
    data: backupMainSchedule,
    isLoading: isBackupMainLoading,
    refetch: refetchBackupMainSchedule,
  } = useBackofficeQuery<BackofficeDatabaseBackupSchedule>(backupMainQueryFn, []);
  const {
    data: backupCloneSchedule,
    isLoading: isBackupCloneLoading,
    refetch: refetchBackupCloneSchedule,
  } = useBackofficeQuery<BackofficeDatabaseBackupSchedule>(backupCloneQueryFn, []);
  const rows = useMemo(() => data?.results ?? [], [data?.results]);
  const backupSchedulesByCode = useMemo<Partial<Record<BackupProfileCode, BackofficeDatabaseBackupSchedule>>>(
    () => ({
      postgresql: backupMainSchedule ?? undefined,
      autodb_clone: backupCloneSchedule ?? undefined,
    }),
    [backupCloneSchedule, backupMainSchedule],
  );
  const isBackupLoading = isBackupMainLoading || isBackupCloneLoading;
  const getDraft = useCallback(
    (item: BackofficeImportSource): ScheduleDraft => drafts[item.id] ?? buildDraft(item),
    [drafts],
  );
  const isRunLocked = useCallback(
    (item: BackofficeImportSource) => Boolean(runningBySource[item.id]) || hasActiveImportRun(item),
    [runningBySource],
  );
  const getBackupProfile = useCallback(
    (profileCode: BackupProfileCode): BackupProfile => {
      return BACKUP_PROFILES.find((profile) => profile.code === profileCode) ?? BACKUP_PROFILES[0];
    },
    [],
  );
  const getBackupSchedule = useCallback(
    (profileCode: BackupProfileCode): BackofficeDatabaseBackupSchedule | null => {
      return backupSchedulesByCode[profileCode] ?? null;
    },
    [backupSchedulesByCode],
  );
  const getBackupDraft = useCallback(
    (profileCode: BackupProfileCode): DatabaseBackupDraft => {
      const draft = backupDraftByCode[profileCode];
      if (draft) {
        return draft;
      }
      return buildBackupDraft(getBackupSchedule(profileCode), getBackupProfile(profileCode));
    },
    [backupDraftByCode, getBackupProfile, getBackupSchedule],
  );
  const getBackupTitle = useCallback(
    (profileCode: BackupProfileCode) => t(`importSchedules.databaseBackup.profiles.${profileCode}.title`),
    [t],
  );
  const isBackupProfileRunning = useCallback(
    (profileCode: BackupProfileCode) => {
      const schedule = getBackupSchedule(profileCode);
      return Boolean(backupRunningByCode[profileCode]) || schedule?.last_status === "running";
    },
    [backupRunningByCode, getBackupSchedule],
  );
  const refreshAfterRunFinished = useCallback(() => {
    void refetch();
  }, [refetch]);
  const refetchBackupSchedule = useCallback(
    async (profileCode: BackupProfileCode) => {
      if (profileCode === "autodb_clone") {
        await refetchBackupCloneSchedule();
        return;
      }
      await refetchBackupMainSchedule();
    },
    [refetchBackupCloneSchedule, refetchBackupMainSchedule],
  );

  async function saveScheduleTime(item: BackofficeImportSource, runTime: string, options?: { silent?: boolean }) {
    if (!token) return;
    const silent = options?.silent === true;
    const sourceLabel = item.code.toUpperCase();
    const normalizedRunTime = runTime || "01:00";
    if (normalizedRunTime === (item.schedule_run_time || "01:00")) {
      return true;
    }

    try {
      await updateBackofficeImportSchedule(token, item.id, {
        schedule_start_date: null,
        schedule_run_time: normalizedRunTime,
        schedule_every_day: true,
        schedule_timezone: item.schedule_timezone || "Europe/Kyiv",
        auto_reprice_after_import: item.auto_reprice_after_import,
        auto_reindex_after_import: item.auto_reindex_after_import,
      });
      if (!silent) {
        showSuccess(t("importSchedules.messages.scheduleSaved", { source: sourceLabel }));
      }
      await refetch();
      return true;
    } catch (error: unknown) {
      showApiError(error, t("importSchedules.messages.actionFailed"));
      return false;
    }
  }

  async function runScenario(item: BackofficeImportSource) {
    if (!token) return;
    if (isRunLocked(item)) return;
    const sourceLabel = item.code.toUpperCase();
    const draft = getDraft(item);
    const scheduleSaved = await saveScheduleTime(item, draft.schedule_run_time, { silent: true });
    if (!scheduleSaved) {
      return;
    }

    try {
      setRunningBySource((prev) => ({ ...prev, [item.id]: true }));
      const response = await runBackofficeImportSchedule(token, item.id, { dispatch_async: true });
      if (response.mode === "async") {
        showSuccess(t("importSchedules.messages.runQueued", { source: sourceLabel }));
      } else {
        const result = (response.result ?? {}) as { status?: string; detail?: string };
        const status = String(result.status || "").toLowerCase();
        if (status && !["success", "partial"].includes(status)) {
          showApiError(result.detail || t("importSchedules.messages.runFailed"), t("importSchedules.messages.runFailed"));
          return;
        }
        showSuccess(t("importSchedules.messages.runCompleted", { source: sourceLabel }));
      }
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("importSchedules.messages.runFailed"));
    } finally {
      setRunningBySource((prev) => ({ ...prev, [item.id]: false }));
    }
  }

  async function toggleAutoImport(item: BackofficeImportSource) {
    if (!token) return;
    const sourceLabel = item.code.toUpperCase();
    const draft = getDraft(item);
    try {
      await updateBackofficeImportSchedule(token, item.id, {
        is_auto_import_enabled: !item.is_auto_import_enabled,
        schedule_start_date: null,
        schedule_run_time: draft.schedule_run_time || item.schedule_run_time || "01:00",
        schedule_every_day: true,
        schedule_timezone: draft.schedule_timezone || item.schedule_timezone || "Europe/Kyiv",
        auto_reprice_after_import: item.auto_reprice_after_import,
        auto_reindex_after_import: item.auto_reindex_after_import,
      });
      showSuccess(t("importSchedules.messages.scheduleUpdated", { source: sourceLabel }));
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("importSchedules.messages.actionFailed"));
    }
  }

  async function saveBackupSchedule(
    profileCode: BackupProfileCode,
    nextDraft: DatabaseBackupDraft = getBackupDraft(profileCode),
    options?: { silent?: boolean },
  ) {
    if (!token) return false;
    try {
      await updateBackofficeDatabaseBackupSchedule(token, {
        is_enabled: nextDraft.is_enabled,
        schedule_run_time: nextDraft.schedule_run_time || getBackupProfile(profileCode).defaultTime,
        schedule_every_day: true,
        schedule_timezone: nextDraft.schedule_timezone || "Europe/Kyiv",
        backup_directory: nextDraft.backup_directory || getBackupProfile(profileCode).defaultDirectory,
        retention_count: Math.max(1, nextDraft.retention_count || 3),
      }, profileCode);
      if (!options?.silent) {
        showSuccess(
          t("importSchedules.databaseBackup.messages.saved", { title: getBackupTitle(profileCode) }),
        );
      }
      setBackupDraftByCode((prev) => {
        const next = { ...prev };
        delete next[profileCode];
        return next;
      });
      await refetchBackupSchedule(profileCode);
      return true;
    } catch (error: unknown) {
      showApiError(
        error,
        t("importSchedules.databaseBackup.messages.actionFailed", { title: getBackupTitle(profileCode) }),
      );
      return false;
    }
  }

  async function toggleBackupSchedule(profileCode: BackupProfileCode) {
    const currentBackupDraft = getBackupDraft(profileCode);
    const nextDraft = {
      ...currentBackupDraft,
      is_enabled: !currentBackupDraft.is_enabled,
    };
    setBackupDraftByCode((prev) => ({ ...prev, [profileCode]: nextDraft }));
    await saveBackupSchedule(profileCode, nextDraft);
  }

  async function runBackupNow(profileCode: BackupProfileCode) {
    const currentBackupDraft = getBackupDraft(profileCode);
    if (!token || isBackupProfileRunning(profileCode)) return;
    try {
      setBackupRunningByCode((prev) => ({ ...prev, [profileCode]: true }));
      await saveBackupSchedule(profileCode, currentBackupDraft, { silent: true });
      await runBackofficeDatabaseBackup(token, { dispatch_async: true }, profileCode);
      showSuccess(
        t("importSchedules.databaseBackup.messages.runQueued", { title: getBackupTitle(profileCode) }),
      );
      await refetchBackupSchedule(profileCode);
    } catch (error: unknown) {
      showApiError(
        error,
        t("importSchedules.databaseBackup.messages.runFailed", { title: getBackupTitle(profileCode) }),
      );
    } finally {
      setBackupRunningByCode((prev) => ({ ...prev, [profileCode]: false }));
    }
  }

  const tableRows = useMemo<ImportScheduleRow[]>(
    () => [
      ...BACKUP_PROFILES.map((profile): ImportScheduleRow => ({ kind: "backup", profileCode: profile.code })),
      ...rows.map((source): ImportScheduleRow => ({ kind: "source", source })),
    ],
    [rows],
  );

  return (
    <section>
      <PageHeader
        title={t("importSchedules.title")}
        description={t("importSchedules.subtitle")}
        actions={
          <button
            type="button"
            className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void refetch();
              void refetchBackupMainSchedule();
              void refetchBackupCloneSchedule();
            }}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
            {t("importSchedules.actions.refresh")}
          </button>
        }
      />

      <div className="mb-3 flex items-center gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-1 py-1">
          <input
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder={t("importSchedules.filters.search")}
            className="h-10 w-[220px] xl:w-[280px] rounded-md border px-3 text-sm shrink-0"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </div>
      </div>

      <AsyncState isLoading={isLoading || isBackupLoading} error={error} empty={!tableRows.length} emptyLabel={t("importSchedules.states.empty")}>
        <BackofficeTable
          emptyLabel={t("importSchedules.states.empty")}
          rows={tableRows}
          columns={[
            {
              key: "source",
              label: t("importSchedules.table.columns.source"),
              render: (row) =>
                row.kind === "backup" ? (
                  <div>
                    <div className="flex items-center gap-2">
                      <DatabaseBackup size={16} />
                      <p className="font-semibold">{getBackupTitle(row.profileCode)}</p>
                    </div>
                  </div>
                ) : (
                  <div>
                    <p className="font-semibold">{row.source.name}</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>
                      {row.source.code} / {row.source.supplier_code}
                    </p>
                  </div>
                ),
            },
            {
              key: "schedule",
              label: t("importSchedules.table.columns.cron"),
              render: (row) => {
                if (row.kind === "backup") {
                  const currentBackupDraft = getBackupDraft(row.profileCode);
                  return (
                    <div className="grid gap-2">
                      <div className="flex items-center gap-2 whitespace-nowrap">
                        <span className="text-xs font-semibold" style={{ color: "var(--muted)" }}>
                          {t("importSchedules.schedule.daily")}
                        </span>
                        <span className="text-xs" style={{ color: "var(--muted)" }}>
                          {currentBackupDraft.schedule_timezone || "Europe/Kyiv"}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <input
                          type="time"
                          value={currentBackupDraft.schedule_run_time}
                          className="h-8 rounded-md border px-2 text-xs"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                          onChange={(event) =>
                            setBackupDraftByCode((prev) => ({
                              ...prev,
                              [row.profileCode]: {
                                ...currentBackupDraft,
                                schedule_run_time: event.target.value,
                              },
                            }))
                          }
                          onBlur={() => {
                            void saveBackupSchedule(row.profileCode);
                          }}
                        />
                      </div>
                    </div>
                  );
                }

                const draft = getDraft(row.source);
                return (
                  <div className="grid gap-2">
                    <div className="flex items-center gap-2 whitespace-nowrap">
                      <span className="text-xs font-semibold" style={{ color: "var(--muted)" }}>
                        {t("importSchedules.schedule.daily")}
                      </span>
                      <span className="text-xs" style={{ color: "var(--muted)" }}>
                        {draft.schedule_timezone || "Europe/Kyiv"}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        type="time"
                        value={draft.schedule_run_time}
                        className="h-8 rounded-md border px-2 text-xs"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                        onChange={(event) => {
                          const value = event.target.value;
                          setDrafts((prev) => ({
                            ...prev,
                            [row.source.id]: {
                              ...(prev[row.source.id] ?? buildDraft(row.source)),
                              schedule_run_time: value,
                            },
                          }));
                        }}
                        onBlur={() => {
                          void saveScheduleTime(row.source, draft.schedule_run_time);
                        }}
                      />
                    </div>
                  </div>
                );
              },
            },
            {
              key: "enabled",
              label: t("importSchedules.table.columns.enabled"),
              render: (row) =>
                row.kind === "backup" ? (
                  <StatusChip status={getBackupDraft(row.profileCode).is_enabled ? "enabled" : "disabled"} />
                ) : (
                  <StatusChip status={row.source.is_auto_import_enabled ? "enabled" : "disabled"} />
                ),
            },
            {
              key: "nextRun",
              label: t("importSchedules.table.columns.nextRun"),
              render: (row) =>
                formatBackofficeDate(
                  row.kind === "backup" ? getBackupSchedule(row.profileCode)?.next_run ?? null : row.source.next_run,
                ),
            },
            {
              key: "status",
              label: t("importSchedules.table.columns.status"),
              render: (row) => {
                if (row.kind === "backup") {
                  const backupSchedule = getBackupSchedule(row.profileCode);
                  return backupSchedule?.last_status ? (
                    <StatusChip
                      status={backupSchedule.last_status}
                      className={isRunningStatus(backupSchedule.last_status) ? "[&>svg]:animate-spin" : ""}
                    />
                  ) : "-";
                }
                return row.source.last_run?.status ? (
                  <StatusChip
                    status={row.source.last_run.status}
                    className={isRunningStatus(row.source.last_run.status) ? "[&>svg]:animate-spin" : ""}
                  />
                ) : "-";
              },
            },
            {
              key: "lastResult",
              label: t("importSchedules.table.columns.lastResult"),
              render: (row) => {
                if (row.kind === "backup") {
                  const backupSchedule = getBackupSchedule(row.profileCode);
                  return (
                  <div>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>
                      {t("importSchedules.databaseBackup.lastSuccess", {
                        value: formatBackofficeDate(backupSchedule?.last_success_at ?? null),
                      })}
                    </p>
                    <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                      {t("importSchedules.databaseBackup.lastFile", { value: backupSchedule?.last_backup_filename || "-" })}
                    </p>
                    <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                      {t("importSchedules.databaseBackup.lastSize", { value: formatBackupSize(backupSchedule?.last_backup_size ?? 0) })}
                    </p>
                    {backupSchedule?.last_message ? (
                      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                        {backupSchedule.last_message}
                      </p>
                    ) : null}
                  </div>
                  );
                }
                return row.source.last_run ? (
                  <div>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>
                      {t("importSchedules.table.lastRunSummary", {
                        rows: row.source.last_run.processed_rows,
                        skipped: row.source.last_run.offers_skipped,
                      })}
                    </p>
                    <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                      {t("importSchedules.table.lastRunStarted", { value: formatBackofficeDate(row.source.last_run.created_at) })}
                    </p>
                    {row.source.last_run.finished_at ? (
                      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                        {t("importSchedules.table.lastRunFinished", { value: formatBackofficeDate(row.source.last_run.finished_at) })}
                      </p>
                    ) : null}
                  </div>
                ) : (
                  "-"
                );
              },
            },
            {
              key: "actions",
              label: t("importSchedules.table.columns.actions"),
              render: (row) =>
                row.kind === "backup" ? (
                  <div className="grid gap-2">
                    {(() => {
                      const currentBackupDraft = getBackupDraft(row.profileCode);
                      const isProfileRunning = isBackupProfileRunning(row.profileCode);
                      return (
                        <>
                    <div className="flex items-center gap-1 whitespace-nowrap">
                      <BackofficeTooltip
                        content={currentBackupDraft.is_enabled ? t("importSchedules.actions.disable") : t("importSchedules.actions.enable")}
                        placement="top"
                        align="center"
                        wrapperClassName="inline-flex"
                      >
                        <button
                          type="button"
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors"
                          aria-label={currentBackupDraft.is_enabled ? t("importSchedules.actions.disable") : t("importSchedules.actions.enable")}
                          style={{
                            borderColor: currentBackupDraft.is_enabled ? monoActiveBackground : "var(--border)",
                            backgroundColor: currentBackupDraft.is_enabled ? monoActiveBackground : "var(--surface)",
                            color: currentBackupDraft.is_enabled ? monoActiveText : "var(--text)",
                          }}
                          onClick={() => {
                            void toggleBackupSchedule(row.profileCode);
                          }}
                          disabled={isBackupLoading}
                        >
                          <Power className="h-4 w-4" />
                        </button>
                      </BackofficeTooltip>
                      <ActionIconButton
                        label={
                          isProfileRunning
                            ? t("importSchedules.databaseBackup.actions.running")
                            : t("importSchedules.databaseBackup.actions.runNow")
                        }
                        icon={Check}
                        onClick={() => {
                          void runBackupNow(row.profileCode);
                        }}
                        disabled={isProfileRunning}
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className="inline-flex h-8 items-center rounded-full border px-1"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      >
                        <BackofficeTooltip content={`${t("importSchedules.databaseBackup.retention")} -`} placement="top" align="center" wrapperClassName="inline-flex">
                          <button
                            type="button"
                            className="inline-flex h-6 w-6 items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50"
                            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                            aria-label={`${t("importSchedules.databaseBackup.retention")} -`}
                            disabled={currentBackupDraft.retention_count <= 1}
                            onClick={() => {
                              const nextDraft = {
                                ...currentBackupDraft,
                                retention_count: Math.max(1, currentBackupDraft.retention_count - 1),
                              };
                              setBackupDraftByCode((prev) => ({ ...prev, [row.profileCode]: nextDraft }));
                              void saveBackupSchedule(row.profileCode, nextDraft, { silent: true });
                            }}
                          >
                            <Minus className="h-3.5 w-3.5" />
                          </button>
                        </BackofficeTooltip>
                        <span className="inline-flex h-6 min-w-[2rem] items-center justify-center px-2 text-xs font-semibold tabular-nums">
                          {currentBackupDraft.retention_count}
                        </span>
                        <BackofficeTooltip content={`${t("importSchedules.databaseBackup.retention")} +`} placement="top" align="center" wrapperClassName="inline-flex">
                          <button
                            type="button"
                            className="inline-flex h-6 w-6 items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50"
                            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                            aria-label={`${t("importSchedules.databaseBackup.retention")} +`}
                            onClick={() => {
                              const nextDraft = {
                                ...currentBackupDraft,
                                retention_count: currentBackupDraft.retention_count + 1,
                              };
                              setBackupDraftByCode((prev) => ({ ...prev, [row.profileCode]: nextDraft }));
                              void saveBackupSchedule(row.profileCode, nextDraft, { silent: true });
                            }}
                          >
                            <Plus className="h-3.5 w-3.5" />
                          </button>
                        </BackofficeTooltip>
                      </div>
                    </div>
                        </>
                      );
                    })()}
                  </div>
                ) : (
                  <div className="flex items-center gap-1 whitespace-nowrap">
                    <BackofficeTooltip
                      content={row.source.is_auto_import_enabled ? t("importSchedules.actions.disable") : t("importSchedules.actions.enable")}
                      placement="top"
                      align="center"
                      wrapperClassName="inline-flex"
                    >
                      <button
                        type="button"
                        className="inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors"
                        aria-label={row.source.is_auto_import_enabled ? t("importSchedules.actions.disable") : t("importSchedules.actions.enable")}
                        style={{
                          borderColor: row.source.is_auto_import_enabled ? monoActiveBackground : "var(--border)",
                          backgroundColor: row.source.is_auto_import_enabled ? monoActiveBackground : "var(--surface)",
                          color: row.source.is_auto_import_enabled ? monoActiveText : "var(--text)",
                        }}
                        onClick={() => {
                          void toggleAutoImport(row.source);
                        }}
                      >
                        <Power className="h-4 w-4" />
                      </button>
                    </BackofficeTooltip>
                    <ScheduleRunActionButton
                      item={row.source}
                      token={token}
                      localRunning={Boolean(runningBySource[row.source.id])}
                      runLabel={t("importSchedules.actions.runNow")}
                      runningLabel={t("importSchedules.actions.runningNow")}
                      onRun={() => {
                        void runScenario(row.source);
                      }}
                      onRunFinished={refreshAfterRunFinished}
                    />
                    <ActionIconButton
                      label={t("importSchedules.actions.saveDefaults")}
                      icon={RotateCcw}
                      onClick={() => {
                        const nextDraft: ScheduleDraft = {
                          schedule_run_time: "01:00",
                          schedule_timezone: "Europe/Kyiv",
                          schedule_every_day: true,
                        };
                        setDrafts((prev) => ({
                          ...prev,
                          [row.source.id]: nextDraft,
                        }));
                        void saveScheduleTime(row.source, nextDraft.schedule_run_time);
                      }}
                    />
                  </div>
                ),
            },
          ]}
        />
      </AsyncState>
    </section>
  );
}
