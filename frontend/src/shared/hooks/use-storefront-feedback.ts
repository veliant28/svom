"use client";

import { useCallback } from "react";

import { useBackofficeToast } from "@/features/backoffice/components/notifications/backoffice-toast-provider";
import { resolveApiErrorMessage } from "@/shared/lib/resolve-api-error-message";

export function useStorefrontFeedback() {
  const toast = useBackofficeToast();

  const showApiError = useCallback(
    (error: unknown, fallbackMessage: string) => {
      const message = resolveApiErrorMessage(error, fallbackMessage);
      toast.error(message);
      return message;
    },
    [toast],
  );

  const showSuccess = useCallback(
    (message: string) => {
      toast.success(message);
    },
    [toast],
  );

  const showError = useCallback(
    (message: string) => {
      toast.error(message);
    },
    [toast],
  );

  const showWarning = useCallback(
    (message: string) => {
      toast.warning(message);
    },
    [toast],
  );

  const showInfo = useCallback(
    (message: string) => {
      toast.info(message);
    },
    [toast],
  );

  return {
    showApiError,
    showError,
    showSuccess,
    showWarning,
    showInfo,
  };
}
