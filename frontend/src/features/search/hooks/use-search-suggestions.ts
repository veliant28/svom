"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { getProducts } from "@/features/catalog/api/get-products";
import type { CatalogProduct } from "@/features/catalog/types";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type UseSearchSuggestionsParams = {
  query: string;
  enabled?: boolean;
  limit?: number;
};

export function useSearchSuggestions({ query, enabled = true, limit = 8 }: UseSearchSuggestionsParams) {
  const locale = useLocale();
  const t = useTranslations("common.header.searchModal.states");
  const { showApiError } = useStorefrontFeedback();
  const [suggestions, setSuggestions] = useState<CatalogProduct[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setSuggestions([]);
      setIsLoading(false);
      return;
    }

    const normalizedQuery = query.trim();
    if (normalizedQuery.length < 2) {
      setSuggestions([]);
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    const timer = window.setTimeout(async () => {
      setIsLoading(true);

      try {
        const response = await getProducts({
          q: normalizedQuery,
          pageSize: limit,
          locale,
        });
        if (isMounted) {
          setSuggestions(response.results);
        }
      } catch (error) {
        if (isMounted) {
          setSuggestions([]);
        }
        showApiError(error, t("error"));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }, 220);

    return () => {
      isMounted = false;
      window.clearTimeout(timer);
    };
  }, [enabled, limit, locale, query, showApiError, t]);

  return {
    suggestions,
    isLoading,
  };
}
