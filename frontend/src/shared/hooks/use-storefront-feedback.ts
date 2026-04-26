"use client";

import { useCallback, useMemo } from "react";
import { useTranslations } from "next-intl";

import { useBackofficeToast } from "@/features/backoffice/components/notifications/backoffice-toast-provider";
import { resolveApiErrorMessage } from "@/shared/lib/resolve-api-error-message";

export function useStorefrontFeedback() {
  const toast = useBackofficeToast();
  const tApiErrors = useTranslations("common.apiErrors");
  const knownApiErrorMessages = useMemo(
    () => ({
      phoneFormat: tApiErrors("phoneFormat"),
      required: tApiErrors("required"),
      notBlank: tApiErrors("notBlank"),
      invalidEmail: tApiErrors("invalidEmail"),
      emailAlreadyExists: tApiErrors("emailAlreadyExists"),
      invalidChoice: tApiErrors("invalidChoice"),
      currentPasswordIncorrect: tApiErrors("currentPasswordIncorrect"),
      maxLength: (max: number) => tApiErrors("maxLength", { max }),
      minLength: (min: number) => tApiErrors("minLength", { min }),
      exactLength: (count: number) => tApiErrors("exactLength", { count }),
    }),
    [tApiErrors],
  );

  const showApiError = useCallback(
    (error: unknown, fallbackMessage: string) => {
      const message = resolveApiErrorMessage(error, fallbackMessage, {
        knownMessages: knownApiErrorMessages,
      });
      toast.error(message);
      return message;
    },
    [knownApiErrorMessages, toast],
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
