import type { Dispatch, SetStateAction } from "react";

import { useProductBulkActions } from "@/features/backoffice/hooks/use-product-bulk-actions";
import type { BackofficeCatalogProduct } from "@/features/backoffice/types/catalog.types";

type BackofficeFeedback = {
  showSuccess: (message: string) => void;
  showApiError: (error: unknown, fallbackMessage?: string) => string;
};

export function useProductsBulkActions({
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
  return useProductBulkActions({
    token,
    rows,
    selectedIds,
    setSelectedIds,
    feedback,
    onAfterDelete,
    refetch,
  });
}
