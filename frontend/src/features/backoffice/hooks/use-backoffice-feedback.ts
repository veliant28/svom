"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";

import { useBackofficeToast } from "@/features/backoffice/components/notifications/backoffice-toast-provider";
import { normalizeBackofficeApiError } from "@/features/backoffice/lib/normalize-backoffice-error";

export function useBackofficeFeedback() {
  const toast = useBackofficeToast();
  const tErrors = useTranslations("backoffice.common.toast.errors");

  const showApiError = useCallback(
    (error: unknown, fallbackMessage?: string) => {
      const normalized = normalizeBackofficeApiError(error, {
        t: tErrors,
        fallbackMessage,
      });
      toast.show({
        variant: normalized.variant,
        message: normalized.message,
      });
      return normalized.message;
    },
    [tErrors, toast],
  );

  const showSuccess = useCallback(
    (message: string) => {
      toast.success(message);
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
    showSuccess,
    showWarning,
    showInfo,
  };
}

