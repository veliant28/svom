import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkActionsOpen, setBulkActionsOpen] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeRawOffers(token, {
        supplier: scope.activeCode,
        latest_only: true,
        q: filters.q,
        category_mapping_status: filters.status === "all" ? undefined : filters.status,
        locale,
        page: filters.page,
        page_size: filters.pageSize,
      }),
    [filters.page, filters.pageSize, filters.q, filters.status, locale, scope.activeCode],
  );

  const {
    token,
    data,
    isLoading,
    error,
    refetch,
  } = useBackofficeQuery<{ count: number; results: BackofficeRawOffer[] }>(
    queryFn,
    [scope.activeCode, locale, filters.page, filters.pageSize, filters.q, filters.status],
  );

  const rows = useMemo(() => data?.results ?? [], [data?.results]);
  const pageRowIds = useMemo(() => rows.map((item) => item.id), [rows]);
  const totalCount = data?.count ?? 0;
  const pagesCount = useMemo(() => Math.max(1, Math.ceil(totalCount / filters.pageSize)), [filters.pageSize, totalCount]);
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const allPageSelected = rows.length > 0 && rows.every((row) => selectedSet.has(row.id));
  const somePageSelected = rows.some((row) => selectedSet.has(row.id));

  const refreshAll = useCallback(async () => {
    await Promise.all([scope.refreshWorkspaceScope(), refetch()]);
  }, [refetch, scope]);

  const handleSupplierCodeChange = useCallback((next: SupplierCode) => {
    scope.setActiveCode(next);
    filters.setPage(1);
    setSelectedIds([]);
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

  const toggleSelected = useCallback((id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }, []);

  const toggleSelectAllPage = useCallback(() => {
    setSelectedIds((prev) => {
      if (pageRowIds.length === 0) {
        return prev;
      }
      const everySelected = pageRowIds.every((id) => prev.includes(id));
      if (everySelected) {
        return prev.filter((id) => !pageRowIds.includes(id));
      }
      const next = new Set(prev);
      for (const id of pageRowIds) {
        next.add(id);
      }
      return Array.from(next);
    });
  }, [pageRowIds]);

  const publishSelected = useCallback(async () => {
    if (!token || isPublishing || selectedIds.length === 0) {
      return;
    }

    setIsPublishing(true);
    try {
      const payload = await publishBackofficeSupplierMappedProducts(token, scope.activeCode, {
        include_needs_review: false,
        dry_run: false,
        reprice_after_publish: true,
        raw_offer_ids: selectedIds,
      });
      const result = payload.result;
      feedback.showSuccess(
        t("productsPage.messages.publishSelectedSuccess", {
          selected: selectedIds.length,
          matched: result.eligible_rows,
          created: result.created_rows,
          updated: result.updated_rows,
          skipped: result.skipped_rows,
          errors: result.error_rows,
        }),
      );
      setBulkActionsOpen(false);
      setSelectedIds([]);
      await refetch();
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("productsPage.messages.publishSelectedFailed"));
    } finally {
      setIsPublishing(false);
    }
  }, [feedback, isPublishing, refetch, scope.activeCode, selectedIds, t, token]);

  useEffect(() => {
    if (!bulkActionsOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!bulkActionsRef.current) {
        return;
      }
      if (bulkActionsRef.current.contains(event.target as Node)) {
        return;
      }
      setBulkActionsOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setBulkActionsOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [bulkActionsOpen]);

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
    selectedSet,
    allPageSelected,
    somePageSelected,
    bulkActionsOpen,
    bulkActionsRef,
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
    publishSelected,
    toggleSelected,
    toggleSelectAllPage,
    setBulkActionsOpen,
    handleSupplierCodeChange,
  };
}
