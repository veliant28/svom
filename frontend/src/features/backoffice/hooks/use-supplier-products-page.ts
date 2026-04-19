import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { getBackofficeRawOffers } from "@/features/backoffice/api/imports-api";
import { publishBackofficeSupplierMappedProducts } from "@/features/backoffice/api/suppliers-api";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useSupplierProductsFilters } from "@/features/backoffice/hooks/use-supplier-products-filters";
import { useSupplierWorkspaceScope, type SupplierCode } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import type { BackofficeRawOffer } from "@/features/backoffice/types/imports.types";

export function useSupplierProductsPage() {
  const t = useTranslations("backoffice.suppliers");
  const tCommon = useTranslations("backoffice.common");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const locale = useLocale();

  const feedback = useBackofficeFeedback();
  const scope = useSupplierWorkspaceScope();
  const filters = useSupplierProductsFilters();

  const [isCategoryMappingOpen, setIsCategoryMappingOpen] = useState(false);
  const [selectedRawOfferId, setSelectedRawOfferId] = useState<string | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeRawOffers(token, {
        supplier: scope.activeCode,
        q: filters.q,
        locale,
        page: filters.page,
        page_size: filters.pageSize,
      }),
    [filters.page, filters.pageSize, filters.q, locale, scope.activeCode],
  );

  const {
    token,
    data,
    isLoading,
    error,
    refetch,
  } = useBackofficeQuery<{ count: number; results: BackofficeRawOffer[] }>(queryFn, [scope.activeCode, locale, filters.page, filters.pageSize, filters.q]);

  const rows = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const pagesCount = useMemo(() => Math.max(1, Math.ceil(totalCount / filters.pageSize)), [filters.pageSize, totalCount]);

  const refreshAll = useCallback(async () => {
    await Promise.all([scope.refreshWorkspaceScope(), refetch()]);
  }, [refetch, scope]);

  const handleSupplierCodeChange = useCallback((next: SupplierCode) => {
    scope.setActiveCode(next);
    filters.setPage(1);
  }, [filters, scope]);

  const openCategoryMapping = useCallback((rawOfferId: string) => {
    setSelectedRawOfferId(rawOfferId);
    setIsCategoryMappingOpen(true);
  }, []);

  const closeCategoryMapping = useCallback(() => {
    setIsCategoryMappingOpen(false);
    setSelectedRawOfferId(null);
  }, []);

  const publishMapped = useCallback(async () => {
    if (!token || isPublishing) {
      return;
    }

    setIsPublishing(true);
    try {
      const payload = await publishBackofficeSupplierMappedProducts(token, scope.activeCode, {
        include_needs_review: false,
        dry_run: false,
        reprice_after_publish: true,
      });
      const result = payload.result;
      feedback.showSuccess(
        t("productsPage.messages.publishSuccess", {
          matched: result.eligible_rows,
          created: result.created_rows,
          updated: result.updated_rows,
          skipped: result.skipped_rows,
          errors: result.error_rows,
        }),
      );
      await refetch();
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("productsPage.messages.publishFailed"));
    } finally {
      setIsPublishing(false);
    }
  }, [feedback, isPublishing, refetch, scope.activeCode, t, token]);

  const publishDisabled = !isHydrated || !token || isPublishing;

  return {
    t,
    tCommon,
    tUtr,
    tGpl,
    locale,
    scope,
    filters,
    token,
    rows,
    totalCount,
    pagesCount,
    isLoading,
    error,
    refetch,
    refreshAll,
    isCategoryMappingOpen,
    selectedRawOfferId,
    openCategoryMapping,
    closeCategoryMapping,
    isPublishing,
    publishDisabled,
    publishMapped,
    handleSupplierCodeChange,
  };
}
