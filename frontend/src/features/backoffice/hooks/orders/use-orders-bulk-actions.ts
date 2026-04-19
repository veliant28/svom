import type { Dispatch, SetStateAction } from "react";

import { useOrderBulkActions } from "@/features/backoffice/hooks/use-order-bulk-actions";
import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";

type OrdersBulkFeedback = {
  showSuccess: (message: string) => void;
  showApiError: (error: unknown, fallbackMessage?: string) => string;
  showWarning: (message: string) => void;
};

export function useOrdersBulkActions({
  token,
  rows,
  selectedIds,
  setSelectedIds,
  feedback,
  onAfterDelete,
  refetch,
}: {
  token: string | null;
  rows: BackofficeOrderOperational[];
  selectedIds: string[];
  setSelectedIds: Dispatch<SetStateAction<string[]>>;
  feedback: OrdersBulkFeedback;
  onAfterDelete: (deletedIds: string[]) => void;
  refetch: () => Promise<unknown>;
}) {
  return useOrderBulkActions({
    token,
    rows,
    selectedIds,
    setSelectedIds,
    feedback,
    onAfterDelete,
    refetch,
  });
}
