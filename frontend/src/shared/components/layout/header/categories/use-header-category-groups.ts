"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale } from "next-intl";

import { getHeaderNavigation } from "@/features/catalog/api/get-categories";
import type { HeaderCategoryParent } from "@/shared/components/layout/header/categories/header-category.types";

export function useHeaderCategoryGroups(initialNavigation: HeaderCategoryParent[] = []) {
  const locale = useLocale();
  const [parents, setParents] = useState<HeaderCategoryParent[]>(initialNavigation);
  const [isLoading, setIsLoading] = useState(initialNavigation.length === 0);
  const lastFetchedLocaleRef = useRef<string | null>(null);
  const hasNavigation = parents.length > 0;

  useEffect(() => {
    if (initialNavigation.length > 0) {
      setParents(initialNavigation);
      setIsLoading(false);
    }
  }, [initialNavigation]);

  useEffect(() => {
    let isMounted = true;

    async function loadNavigation() {
      if (lastFetchedLocaleRef.current === locale) {
        return;
      }
      lastFetchedLocaleRef.current = locale;
      if (!hasNavigation) {
        setIsLoading(true);
      }
      try {
        const data = await getHeaderNavigation(locale);
        if (isMounted) {
          setParents((current) => {
            if (!Array.isArray(data) || data.length === 0) {
              return current;
            }
            return data;
          });
        }
      } catch {
        // Keep server-rendered categories visible if the client refresh fails.
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadNavigation();

    return () => {
      isMounted = false;
    };
  }, [hasNavigation, locale]);

  const visibleParents = useMemo(() => parents.filter((parent) => parent.sections.length > 0), [parents]);

  return {
    parents: visibleParents,
    isLoading,
  };
}
