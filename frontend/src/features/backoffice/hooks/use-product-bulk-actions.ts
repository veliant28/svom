import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { useTranslations } from "next-intl";

import {
  deleteBackofficeCatalogProduct,
  runBulkMoveProductsCategoryAction,
  runReindexProductsAction,
} from "@/features/backoffice/api/catalog-api";
import type { BackofficeCatalogProduct } from "@/features/backoffice/types/catalog.types";

type BackofficeFeedback = {
  showSuccess: (message: string) => void;
  showApiError: (error: unknown, fallbackMessage?: string) => string;
};

export function useProductBulkActions({
  token,
  rows,
  selectedIds,
  setSelectedIds,
  feedback,
  onAfterDelete,
  refetch,
}: {
  token: string | null;
  rows: BackofficeCatalogProduct[];
  selectedIds: string[];
  setSelectedIds: Dispatch<SetStateAction<string[]>>;
  feedback: BackofficeFeedback;
  onAfterDelete: (deletedIds: string[]) => void;
  refetch: () => Promise<unknown>;
}) {
  const t = useTranslations("backoffice.common");

  const [runningAction, setRunningAction] = useState<"move_category" | "reindex" | "delete" | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkMoveCategoryOpen, setBulkMoveCategoryOpen] = useState(false);
  const [bulkTargetCategoryId, setBulkTargetCategoryId] = useState("");
  const [bulkActionsOpen, setBulkActionsOpen] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement | null>(null);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const allPageSelected = rows.length > 0 && rows.every((row) => selectedSet.has(row.id));
  const somePageSelected = rows.some((row) => selectedSet.has(row.id));

  const toggleSelected = useCallback((id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }, [setSelectedIds]);

  const toggleSelectAllPage = useCallback(() => {
    setSelectedIds((prev) => {
      if (rows.length === 0) {
        return prev;
      }
      const pageIds = rows.map((item) => item.id);
      const everySelected = pageIds.every((id) => prev.includes(id));
      if (everySelected) {
        return prev.filter((id) => !pageIds.includes(id));
      }
      const next = new Set(prev);
      for (const id of pageIds) {
        next.add(id);
      }
      return Array.from(next);
    });
  }, [rows, setSelectedIds]);

  const runBulkReindex = useCallback(async () => {
    if (!token || selectedIds.length === 0 || runningAction) {
      return;
    }
    setRunningAction("reindex");
    try {
      await runReindexProductsAction(token, { product_ids: selectedIds, dispatch_async: true });
      feedback.showSuccess(t("products.messages.reindexQueued", { count: selectedIds.length }));
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("products.messages.reindexFailed"));
    } finally {
      setRunningAction(null);
    }
  }, [feedback, runningAction, selectedIds, t, token]);

  const runBulkMoveCategory = useCallback(async () => {
    if (!token || selectedIds.length === 0 || runningAction) {
      return;
    }
    if (!bulkTargetCategoryId) {
      feedback.showApiError(new Error("category_required"), t("products.messages.bulkMoveCategoryRequired"));
      return;
    }

    setRunningAction("move_category");
    try {
      const result = await runBulkMoveProductsCategoryAction(token, {
        product_ids: selectedIds,
        category_id: bulkTargetCategoryId,
        update_import_rules: true,
      });
      await refetch();
      feedback.showSuccess(
        t("products.messages.bulkMoveCategoryDone", {
          products: result.products_updated,
          offers: result.raw_offers_updated,
        }),
      );
      setBulkMoveCategoryOpen(false);
      setBulkTargetCategoryId("");
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("products.messages.bulkMoveCategoryFailed"));
    } finally {
      setRunningAction(null);
    }
  }, [bulkTargetCategoryId, feedback, refetch, runningAction, selectedIds, t, token]);

  const runBulkDelete = useCallback(async () => {
    if (!token || selectedIds.length === 0 || runningAction) {
      if (selectedIds.length === 0) {
        setBulkDeleteOpen(false);
      }
      return;
    }

    const idsToDelete = [...selectedIds];
    setRunningAction("delete");
    try {
      let deletedCount = 0;
      for (const productId of idsToDelete) {
        try {
          await deleteBackofficeCatalogProduct(token, productId);
          deletedCount += 1;
        } catch {
          // Continue deleting the rest to avoid leaving the batch half-processed.
        }
      }

      const failedCount = idsToDelete.length - deletedCount;
      if (deletedCount > 0) {
        setSelectedIds((prev) => prev.filter((id) => !idsToDelete.includes(id)));
        onAfterDelete(idsToDelete);
        await refetch();
      }

      if (failedCount === 0) {
        feedback.showSuccess(t("products.messages.bulkDeleted", { count: deletedCount }));
      } else {
        feedback.showApiError(
          new Error(t("products.messages.bulkDeletePartial", { deleted: deletedCount, failed: failedCount })),
          t("products.messages.bulkDeleteFailed"),
        );
      }
    } finally {
      setRunningAction(null);
      setBulkDeleteOpen(false);
    }
  }, [feedback, onAfterDelete, refetch, runningAction, selectedIds, setSelectedIds, t, token]);

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

  return {
    selectedSet,
    allPageSelected,
    somePageSelected,
    runningAction,
    bulkDeleteOpen,
    bulkMoveCategoryOpen,
    bulkTargetCategoryId,
    bulkActionsOpen,
    bulkActionsRef,
    setBulkDeleteOpen,
    setBulkMoveCategoryOpen,
    setBulkTargetCategoryId,
    setBulkActionsOpen,
    toggleSelected,
    toggleSelectAllPage,
    runBulkMoveCategory,
    runBulkReindex,
    runBulkDelete,
  };
}
