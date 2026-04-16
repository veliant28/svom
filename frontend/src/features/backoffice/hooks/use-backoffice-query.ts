"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";

export function useBackofficeQuery<T>(queryFn: (token: string) => Promise<T>, deps: unknown[] = []) {
  const t = useTranslations("backoffice.common");
  const { token, isLoading: isAuthLoading } = useAuth();
  const { showApiError } = useBackofficeFeedback();
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(async () => {
    if (!token) {
      setData(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await queryFn(token);
      setData(result);
    } catch (err: unknown) {
      setError(showApiError(err, t("requestFailed")));
    } finally {
      setIsLoading(false);
    }
  }, [token, queryFn, showApiError, t]);

  useEffect(() => {
    if (isAuthLoading) {
      return;
    }

    void execute();
  }, [execute, isAuthLoading, ...deps]);

  return {
    token,
    data,
    isLoading: isLoading || isAuthLoading,
    error,
    refetch: execute,
  };
}
