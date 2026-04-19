import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeImportSchedules } from "@/features/backoffice/api/imports-api";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useSupplierActions } from "@/features/backoffice/hooks/use-supplier-actions";
import { useSupplierWorkspaceScope } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import { useTokenCountdown } from "@/features/backoffice/hooks/use-token-countdown";
import { formatSupplierTokenCountdown } from "@/features/backoffice/lib/suppliers/supplier-formatters";
import {
  resolveSupplierConnectionLabel,
  resolveSupplierTokenStateLabel,
  supplierTokenCountdownTone,
} from "@/features/backoffice/lib/suppliers/supplier-status";
import type { BackofficeImportSource } from "@/features/backoffice/types/imports.types";

export function useSuppliersPage() {
  const t = useTranslations("backoffice.suppliers");
  const tAuth = useTranslations("backoffice.auth");
  const tCommon = useTranslations("backoffice.common");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const tErrors = useTranslations("backoffice.errors");

  const scope = useSupplierWorkspaceScope();

  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [fingerprint, setFingerprint] = useState("svom-backoffice");
  const [isEnabled, setIsEnabled] = useState(true);

  useEffect(() => {
    if (!scope.workspace) {
      return;
    }
    setLogin(scope.workspace.connection.login ?? "");
    setIsEnabled(scope.workspace.supplier.is_enabled);
  }, [scope.workspace]);

  const schedulesQuery = useCallback((apiToken: string) => getBackofficeImportSchedules(apiToken), []);
  const {
    data: schedulesData,
    isLoading: schedulesLoading,
    error: schedulesError,
    refetch: refetchSchedules,
  } = useBackofficeQuery<{ count: number; results: BackofficeImportSource[] }>(schedulesQuery, []);

  const supplierScheduleRows = useMemo(
    () => (schedulesData?.results ?? []).filter((item) => item.supplier_code === scope.activeCode),
    [scope.activeCode, schedulesData],
  );

  const actions = useSupplierActions({
    token: scope.token,
    activeCode: scope.activeCode,
    tAuth,
    tCommon,
    tErrors,
    refreshWorkspaceScope: scope.refreshWorkspaceScope,
    refetchSchedules,
  });

  const handleSaveSettings = useCallback(async () => {
    if (!scope.token) {
      return;
    }

    await actions.saveSettings({
      login,
      password,
      fingerprint,
      isEnabled,
    });

    setPassword("");
  }, [actions, fingerprint, isEnabled, login, password, scope.token]);

  const accessSecondsLeft = useTokenCountdown(scope.workspace?.connection.access_token_expires_at);
  const accessTone = supplierTokenCountdownTone(accessSecondsLeft);

  const connectionLabel = useMemo(
    () => resolveSupplierConnectionLabel(scope.workspace?.connection.status, tCommon),
    [scope.workspace?.connection.status, tCommon],
  );

  const tokenStateLabel = useMemo(
    () => resolveSupplierTokenStateLabel(accessTone, tCommon),
    [accessTone, tCommon],
  );

  const tokenCountdownLabel = useMemo(
    () => formatSupplierTokenCountdown(accessSecondsLeft, tAuth),
    [accessSecondsLeft, tAuth],
  );

  return {
    t,
    tAuth,
    tCommon,
    tUtr,
    tGpl,
    scope,
    schedulesLoading,
    schedulesError,
    supplierScheduleRows,
    actions,
    login,
    setLogin,
    password,
    setPassword,
    fingerprint,
    setFingerprint,
    isEnabled,
    setIsEnabled,
    handleSaveSettings,
    accessSecondsLeft,
    accessTone,
    connectionLabel,
    tokenStateLabel,
    tokenCountdownLabel,
  };
}
