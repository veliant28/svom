import { useCallback } from "react";

import { updateBackofficeImportSchedule } from "@/features/backoffice/api/imports-api";
import {
  checkBackofficeSupplierConnection,
  obtainBackofficeSupplierToken,
  refreshBackofficeSupplierToken,
  updateBackofficeSupplierSettings,
} from "@/features/backoffice/api/suppliers-api";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { buildDefaultImportSchedulePayload, buildSupplierSettingsPayload } from "@/features/backoffice/lib/suppliers/supplier-auth-utils";
import type { BackofficeImportSource } from "@/features/backoffice/types/imports.types";
import type { SupplierCode } from "@/features/backoffice/hooks/use-supplier-workspace-scope";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function useSupplierActions({
  token,
  activeCode,
  tAuth,
  tCommon,
  tErrors,
  refreshWorkspaceScope,
  refetchSchedules,
}: {
  token: string | null;
  activeCode: SupplierCode;
  tAuth: Translator;
  tCommon: Translator;
  tErrors: Translator;
  refreshWorkspaceScope: () => Promise<unknown>;
  refetchSchedules?: () => Promise<unknown>;
}) {
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const runWorkspaceAction = useCallback(
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

  const saveSettings = useCallback(async ({
    login,
    password,
    fingerprint,
    isEnabled,
  }: {
    login: string;
    password: string;
    fingerprint: string;
    isEnabled: boolean;
  }) => {
    if (!token) {
      return;
    }

    await runWorkspaceAction(
      () => updateBackofficeSupplierSettings(token, activeCode, buildSupplierSettingsPayload({
        login,
        password,
        fingerprint,
        isEnabled,
      })),
      {
        successMessage: tAuth("messages.settingsSaved"),
        errorFallback: tAuth("messages.settingsSaveFailed"),
      },
    );
  }, [activeCode, runWorkspaceAction, tAuth, token]);

  const obtainToken = useCallback(async () => {
    if (!token) {
      return;
    }

    await runWorkspaceAction(
      () => obtainBackofficeSupplierToken(token, activeCode),
      {
        successMessage: tAuth("messages.tokenObtained"),
        errorFallback: tAuth("messages.tokenObtainFailed"),
      },
    );
  }, [activeCode, runWorkspaceAction, tAuth, token]);

  const refreshToken = useCallback(async () => {
    if (!token) {
      return;
    }

    await runWorkspaceAction(
      () => refreshBackofficeSupplierToken(token, activeCode),
      {
        successMessage: tAuth("messages.tokenRefreshed"),
        errorFallback: tAuth("messages.tokenRefreshFailed"),
      },
    );
  }, [activeCode, runWorkspaceAction, tAuth, token]);

  const checkConnection = useCallback(async () => {
    if (!token) {
      return;
    }

    await runWorkspaceAction(
      () => checkBackofficeSupplierConnection(token, activeCode),
      {
        successMessage: tAuth("messages.connectionChecked"),
        errorFallback: tAuth("messages.connectionCheckFailed"),
      },
    );
  }, [activeCode, runWorkspaceAction, tAuth, token]);

  const toggleAutoImport = useCallback(async (item: BackofficeImportSource) => {
    if (!token) {
      return;
    }
    const sourceLabel = item.code.toUpperCase();

    try {
      await updateBackofficeImportSchedule(token, item.id, {
        is_auto_import_enabled: !item.is_auto_import_enabled,
      });
      showSuccess(tCommon("importSchedules.messages.scheduleUpdated", { source: sourceLabel }));
      if (refetchSchedules) {
        await refetchSchedules();
      }
    } catch (error: unknown) {
      showApiError(error, tCommon("importSchedules.messages.actionFailed"));
    }
  }, [refetchSchedules, showApiError, showSuccess, tCommon, token]);

  const saveDefaultCron = useCallback(async (item: BackofficeImportSource) => {
    if (!token) {
      return;
    }
    const sourceLabel = item.code.toUpperCase();

    try {
      await updateBackofficeImportSchedule(token, item.id, buildDefaultImportSchedulePayload(item));
      showSuccess(tCommon("importSchedules.messages.scheduleSaved", { source: sourceLabel }));
      if (refetchSchedules) {
        await refetchSchedules();
      }
    } catch (error: unknown) {
      showApiError(error, tCommon("importSchedules.messages.actionFailed"));
    }
  }, [refetchSchedules, showApiError, showSuccess, tCommon, token]);

  return {
    saveSettings,
    obtainToken,
    refreshToken,
    checkConnection,
    toggleAutoImport,
    saveDefaultCron,
  };
}
