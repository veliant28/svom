"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { isApiRequestError } from "@/shared/api/http-client";

const RETRYABLE_STATUSES = new Set([408, 425, 429, 500, 502, 503, 504]);
const MAX_ATTEMPTS = 2;

function wait(ms: number) {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}

function shouldRetry(error: unknown): boolean {
  if (!isApiRequestError(error)) {
    return false;
  }
  if (error.isNetworkError) {
    return true;
  }
  if (typeof error.status !== "number") {
    return false;
  }
  return RETRYABLE_STATUSES.has(error.status);
}

export function useBackofficeQuery<T>(queryFn: (token: string) => Promise<T>, deps: unknown[] = []) {
  const t = useTranslations("backoffice.common");
  const { token, isLoading: isAuthLoading } = useAuth();
  const { showApiError } = useBackofficeFeedback();
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const execute = useCallback(async () => {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    if (!token) {
      if (mountedRef.current) {
        setData(null);
        setError(null);
        setIsLoading(false);
      }
      return;
    }

    if (mountedRef.current) {
      setIsLoading(true);
      setError(null);
    }

    try {
      let result: T | null = null;
      let resolved = false;
      let lastError: unknown;

      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
        try {
          result = await queryFn(token);
          resolved = true;
          break;
        } catch (err: unknown) {
          lastError = err;
          if (attempt >= MAX_ATTEMPTS || !shouldRetry(err)) {
            throw err;
          }
          await wait(250 * attempt);
        }
      }

      if (!resolved) {
        throw lastError;
      }

      if (!mountedRef.current || requestId !== requestIdRef.current) {
        return;
      }
      setData(result as T);
    } catch (err: unknown) {
      if (!mountedRef.current || requestId !== requestIdRef.current) {
        return;
      }
      setError(showApiError(err, t("requestFailed")));
    } finally {
      if (!mountedRef.current || requestId !== requestIdRef.current) {
        return;
      }
      setIsLoading(false);
    }
  }, [token, queryFn, showApiError, t]);

  const depsSignature = useMemo(() => {
    try {
      return JSON.stringify(deps);
    } catch {
      return String(deps.length);
    }
  }, [deps]);

  useEffect(() => {
    if (isAuthLoading) {
      return;
    }

    void execute();
  }, [depsSignature, execute, isAuthLoading]);

  return {
    token,
    data,
    isLoading: isLoading || isAuthLoading,
    error,
    refetch: execute,
  };
}
