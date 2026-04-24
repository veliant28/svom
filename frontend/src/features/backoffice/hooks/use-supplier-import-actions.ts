import { useCallback } from "react";

import {
  deleteBackofficeSupplierPriceList,
  downloadBackofficeSupplierPriceList,
  importBackofficeSupplierPriceListToRaw,
  requestBackofficeSupplierPriceList,
} from "@/features/backoffice/api/suppliers-api";
import type { SupplierCode } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import { buildRequestPayloadFromRow } from "@/features/backoffice/lib/supplier-import/supplier-import-formatters";
import type { BackofficeSupplierPriceList } from "@/features/backoffice/types/suppliers.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

type BackofficeFeedback = {
  showSuccess: (message: string) => void;
  showWarning: (message: string) => void;
  showApiError: (error: unknown, fallbackMessage?: string) => string;
};

export function useSupplierImportActions({
  token,
  tokenReady,
  activeCode,
  requestPayload,
  feedback,
  t,
  tErrors,
  refreshWorkspaceAndParams,
  refetchPriceLists,
}: {
  token: string | null;
  tokenReady: boolean;
  activeCode: SupplierCode;
  requestPayload: {
    format: string;
    in_stock: boolean;
    show_scancode: boolean;
    utr_article: boolean;
    visible_brands: number[];
    categories: string[];
    models_filter: string[];
  };
  feedback: BackofficeFeedback;
  t: Translator;
  tErrors: Translator;
  refreshWorkspaceAndParams: () => Promise<unknown>;
  refetchPriceLists: () => Promise<unknown>;
}) {
  const runAction = useCallback(
    async <T,>(
      action: () => Promise<T>,
      options: {
        successMessage: string;
        errorFallback?: string;
        refreshPriceLists?: boolean;
      },
    ) => {
      try {
        await action();
        feedback.showSuccess(options.successMessage);
        if (options.refreshPriceLists) {
          await Promise.all([refreshWorkspaceAndParams(), refetchPriceLists()]);
        } else {
          await refreshWorkspaceAndParams();
        }
      } catch (error: unknown) {
        feedback.showApiError(error, options.errorFallback ?? tErrors("actions.failed"));
      }
    },
    [feedback, refetchPriceLists, refreshWorkspaceAndParams, tErrors],
  );

  const requestLatest = useCallback(async () => {
    if (!tokenReady || !token) {
      return;
    }

    await runAction(
      () => requestBackofficeSupplierPriceList(token, activeCode, requestPayload),
      {
        successMessage: t("priceLifecycle.messages.requested"),
        errorFallback: t("priceLifecycle.messages.requestFailed"),
      },
    );
  }, [activeCode, requestPayload, runAction, t, token, tokenReady]);

  const downloadById = useCallback(async (priceListId: string, refreshPriceLists = false) => {
    if (!tokenReady || !token) {
      return;
    }

    await runAction(
      () => downloadBackofficeSupplierPriceList(token, activeCode, priceListId),
      {
        successMessage: t("priceLifecycle.messages.downloaded"),
        errorFallback: t("priceLifecycle.messages.downloadFailed"),
        refreshPriceLists,
      },
    );
  }, [activeCode, runAction, t, token, tokenReady]);

  const importById = useCallback(async (priceListId: string, refreshPriceLists = false) => {
    if (!tokenReady || !token) {
      return;
    }

    await runAction(
      () => importBackofficeSupplierPriceListToRaw(token, activeCode, priceListId),
      {
        successMessage: t("priceLifecycle.messages.imported"),
        errorFallback: t("priceLifecycle.messages.importFailed"),
        refreshPriceLists,
      },
    );
  }, [activeCode, runAction, t, token, tokenReady]);

  const requestFromRow = useCallback(async (item: BackofficeSupplierPriceList) => {
    if (!tokenReady || !token) {
      return;
    }

    await runAction(
      () => requestBackofficeSupplierPriceList(
        token,
        activeCode,
        buildRequestPayloadFromRow({ item }),
      ),
      {
        successMessage: t("priceLifecycle.messages.requested"),
        errorFallback: t("priceLifecycle.messages.requestFailed"),
        refreshPriceLists: true,
      },
    );
  }, [activeCode, runAction, t, token, tokenReady]);

  const downloadFromRow = useCallback(async (item: BackofficeSupplierPriceList) => {
    await downloadById(item.id, true);
  }, [downloadById]);

  const importFromRow = useCallback(async (item: BackofficeSupplierPriceList) => {
    await importById(item.id, true);
  }, [importById]);

  const deleteFromRow = useCallback(async (item: BackofficeSupplierPriceList) => {
    if (!tokenReady || !token) {
      return;
    }

    try {
      const result = await deleteBackofficeSupplierPriceList(token, activeCode, item.id);
      if (!result.deleted_remote && result.remote_delete_error) {
        feedback.showWarning(
          t("priceLifecycle.messages.deletedLocalOnly", {
            reason: result.remote_delete_error,
          }),
        );
      } else {
        feedback.showSuccess(t("priceLifecycle.messages.deleted"));
      }
      await Promise.all([refreshWorkspaceAndParams(), refetchPriceLists()]);
    } catch (error: unknown) {
      feedback.showApiError(error, t("priceLifecycle.messages.deleteFailed"));
    }
  }, [activeCode, feedback, refetchPriceLists, refreshWorkspaceAndParams, t, token, tokenReady]);

  return {
    requestLatest,
    downloadById,
    importById,
    requestFromRow,
    downloadFromRow,
    importFromRow,
    deleteFromRow,
  };
}
