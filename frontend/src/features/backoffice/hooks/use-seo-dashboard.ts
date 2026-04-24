"use client";

import { useCallback } from "react";

import { getBackofficeSeoDashboard } from "@/features/backoffice/api/seo-api";
import type { BackofficeSeoDashboard } from "@/features/backoffice/api/seo-api.types";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";

export function useSeoDashboard() {
  const queryFn = useCallback((token: string) => getBackofficeSeoDashboard(token), []);
  return useBackofficeQuery<BackofficeSeoDashboard>(queryFn, []);
}
