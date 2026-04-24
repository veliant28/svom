import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeSupplierPriceListParams,
  getBackofficeSupplierPriceLists,
} from "@/features/backoffice/api/suppliers-api";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useSupplierImportActions } from "@/features/backoffice/hooks/use-supplier-import-actions";
import { useSupplierImportFilters } from "@/features/backoffice/hooks/use-supplier-import-filters";
import { useSupplierWorkspaceScope } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import { resolveParamsSourceLabel } from "@/features/backoffice/lib/supplier-import/supplier-import-formatters";
import { findLatestPriceListStats } from "@/features/backoffice/lib/supplier-import/supplier-import-status";
import type { BackofficeSupplierPriceList, BackofficeSupplierPriceListParams } from "@/features/backoffice/types/suppliers.types";

export function useSupplierImportPage() {
  const t = useTranslations("backoffice.suppliers");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const tErrors = useTranslations("backoffice.errors");

  const feedback = useBackofficeFeedback();

  const scope = useSupplierWorkspaceScope();

  const paramsQuery = useCallback(
    (apiToken: string) => getBackofficeSupplierPriceListParams(apiToken, scope.activeCode),
    [scope.activeCode],
  );

  const {
    data: supplierParams,
    refetch: refetchSupplierParams,
  } = useBackofficeQuery<BackofficeSupplierPriceListParams>(paramsQuery, [scope.activeCode]);

  const priceListsQuery = useCallback(
    (apiToken: string) => getBackofficeSupplierPriceLists(apiToken, scope.activeCode),
    [scope.activeCode],
  );

  const {
    data: priceListsData,
    isLoading: priceListsLoading,
    error: priceListsError,
    refetch: refetchPriceLists,
  } = useBackofficeQuery<{ count: number; results: BackofficeSupplierPriceList[] }>(priceListsQuery, [scope.activeCode]);

  const refreshWorkspaceAndParams = useCallback(async () => {
    await Promise.all([scope.refreshWorkspaceScope(), refetchSupplierParams()]);
  }, [refetchSupplierParams, scope]);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshWorkspaceAndParams(), refetchPriceLists()]);
  }, [refetchPriceLists, refreshWorkspaceAndParams]);

  const filters = useSupplierImportFilters({
    activeCode: scope.activeCode,
    supplierParams,
  });

  const tokenReady = filters.tokenReady && Boolean(scope.token);

  const rows = useMemo(() => priceListsData?.results ?? [], [priceListsData?.results]);
  const lifecycle = useMemo(() => findLatestPriceListStats(rows), [rows]);

  const cooldownCanRun = scope.workspace?.cooldown.can_run ?? true;
  const cooldownWaitSeconds = scope.workspace?.cooldown.wait_seconds ?? 0;
  const [cooldownSecondsLeft, setCooldownSecondsLeft] = useState(Math.max(0, Math.floor(cooldownWaitSeconds)));

  useEffect(() => {
    setCooldownSecondsLeft(Math.max(0, Math.floor(cooldownWaitSeconds)));
  }, [cooldownWaitSeconds]);

  useEffect(() => {
    if (!filters.isUtr || cooldownCanRun || cooldownSecondsLeft <= 0) {
      return;
    }

    const timer = window.setInterval(() => {
      setCooldownSecondsLeft((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [cooldownCanRun, cooldownSecondsLeft, filters.isUtr]);

  const actions = useSupplierImportActions({
    token: scope.token,
    tokenReady,
    activeCode: scope.activeCode,
    requestPayload: filters.requestPayload,
    feedback,
    t,
    tErrors,
    refreshWorkspaceAndParams,
    refetchPriceLists,
  });

  const paramsSourceLabel = useMemo(
    () => resolveParamsSourceLabel(supplierParams?.source, t),
    [supplierParams?.source, t],
  );

  const requestPrimary = actions.requestLatest;
  const downloadPrimary = useCallback(async () => {
    if (!lifecycle.firstDownloadable) {
      return;
    }
    await actions.downloadById(lifecycle.firstDownloadable.id);
  }, [actions, lifecycle.firstDownloadable]);

  const importPrimary = useCallback(async () => {
    if (!lifecycle.firstImportable) {
      return;
    }
    await actions.importById(lifecycle.firstImportable.id);
  }, [actions, lifecycle.firstImportable]);

  return {
    t,
    tUtr,
    tGpl,
    tErrors,
    feedback,
    scope,
    supplierParams,
    rows,
    priceListsLoading,
    priceListsError,
    refetchPriceLists,
    refreshWorkspaceAndParams,
    refreshAll,
    tokenReady,
    filters,
    actions,
    lifecycle,
    paramsSourceLabel,
    requestPrimary,
    downloadPrimary,
    importPrimary,
    cooldownCanRun,
    cooldownSecondsLeft,
  };
}
