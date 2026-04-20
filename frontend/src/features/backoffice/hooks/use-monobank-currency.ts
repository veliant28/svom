"use client";

import { useCallback, useEffect, useState } from "react";

import { getBackofficeMonobankCurrency } from "@/features/backoffice/api/payment-api";
import type { BackofficeMonobankCurrencyResponse } from "@/features/backoffice/types/payment.types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";

const CURRENCY_REFRESH_COOLDOWN_SECONDS = 10;

function extractCooldownSecondsFromMessage(message: string): number | null {
  const match = message.match(/(\d{1,6})\s*(sec|secs|second|seconds|сек|секунд|с)\b/i);
  if (!match) {
    return null;
  }
  const value = Number(match[1]);
  if (!Number.isFinite(value) || value <= 0) {
    return null;
  }
  return Math.ceil(value);
}

export function useMonobankCurrency({ t }: { t: (key: string, values?: Record<string, string | number>) => string }) {
  const { token } = useAuth();
  const { showApiError, showWarning } = useBackofficeFeedback();
  const [data, setData] = useState<BackofficeMonobankCurrencyResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshCooldown, setIsRefreshCooldown] = useState(false);

  const load = useCallback(async (forceRefresh = false) => {
    if (!token) {
      setData(null);
      setIsLoading(false);
      return;
    }
    if (forceRefresh && isRefreshCooldown) {
      showWarning(t("toast.errors.cooldownSeconds", { seconds: CURRENCY_REFRESH_COOLDOWN_SECONDS }));
      return;
    }
    setIsLoading(true);
    try {
      const payload = await getBackofficeMonobankCurrency(token, forceRefresh ? { refresh: true } : undefined);
      setData(payload);
      if (forceRefresh) {
        setIsRefreshCooldown(true);
        window.setTimeout(() => setIsRefreshCooldown(false), CURRENCY_REFRESH_COOLDOWN_SECONDS * 1000);
      }
    } catch (error) {
      const message = showApiError(error, t("payments.messages.currencyFailed"));
      if (/слишком рано|too early|cooldown|rate limit|429/i.test(message)) {
        const seconds = extractCooldownSecondsFromMessage(message) ?? CURRENCY_REFRESH_COOLDOWN_SECONDS;
        setIsRefreshCooldown(true);
        window.setTimeout(() => setIsRefreshCooldown(false), Math.max(1, seconds) * 1000);
      }
    } finally {
      setIsLoading(false);
    }
  }, [isRefreshCooldown, showApiError, showWarning, t, token]);

  useEffect(() => {
    void load(false);
  }, [load]);

  return {
    data,
    isLoading,
    isRefreshCooldown,
    refresh: () => load(true),
  };
}
