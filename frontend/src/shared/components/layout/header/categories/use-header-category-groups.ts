"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale } from "next-intl";

import { getCategories } from "@/features/catalog/api/get-categories";
import type { CategorySummary } from "@/features/catalog/types";
import type {
  HeaderCategoryParent,
  HeaderCategorySection,
} from "@/shared/components/layout/header/categories/header-category.types";

function groupCategoriesByParent(categories: CategorySummary[]): HeaderCategoryParent[] {
  const childrenByParentId = new Map<string, CategorySummary[]>();

  categories.forEach((category) => {
    if (!category.parent) {
      return;
    }
    const bucket = childrenByParentId.get(category.parent.id) ?? [];
    bucket.push(category);
    childrenByParentId.set(category.parent.id, bucket);
  });

  function collectDescendantNodes(categoryId: string): CategorySummary[] {
    const children = [...(childrenByParentId.get(categoryId) ?? [])].sort((left, right) =>
      left.name.localeCompare(right.name),
    );
    if (children.length === 0) {
      return [];
    }

    return children.flatMap((child) => [child, ...collectDescendantNodes(child.id)]);
  }

  const roots = categories
    .filter((category) => !category.parent)
    .sort((left, right) => left.name.localeCompare(right.name));

  return roots.map((root) => {
    const directChildren = [...(childrenByParentId.get(root.id) ?? [])].sort((left, right) =>
      left.name.localeCompare(right.name),
    );

    const directLeafs: CategorySummary[] = [];
    const groupedSections: HeaderCategorySection[] = [];

    directChildren.forEach((child) => {
      const descendants = collectDescendantNodes(child.id);
      if (descendants.length === 0) {
        directLeafs.push(child);
        return;
      }

      groupedSections.push({
        id: `${root.id}-${child.id}`,
        title: child.name,
        items: descendants,
      });
    });

    const sections: HeaderCategorySection[] = [];
    sections.push(...groupedSections);

    if (directLeafs.length > 0) {
      sections.push({
        id: `${root.id}-direct`,
        title: null,
        items: directLeafs,
      });
    }

    return {
      id: root.id,
      name: root.name,
      slug: root.slug,
      sections,
    };
  });
}

export function useHeaderCategoryGroups(initialCategories: CategorySummary[] = []) {
  const locale = useLocale();
  const [categories, setCategories] = useState<CategorySummary[]>(initialCategories);
  const [isLoading, setIsLoading] = useState(initialCategories.length === 0);
  const lastFetchedLocaleRef = useRef<string | null>(null);
  const hasCategories = categories.length > 0;

  useEffect(() => {
    if (initialCategories.length > 0) {
      setCategories(initialCategories);
      setIsLoading(false);
    }
  }, [initialCategories]);

  useEffect(() => {
    let isMounted = true;

    async function loadCategories() {
      if (hasCategories) {
        lastFetchedLocaleRef.current = locale;
        setIsLoading(false);
        return;
      }
      if (lastFetchedLocaleRef.current === locale) {
        return;
      }
      lastFetchedLocaleRef.current = locale;
      setIsLoading(true);
      try {
        const data = await getCategories(locale);
        if (isMounted) {
          setCategories((current) => {
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

    void loadCategories();

    return () => {
      isMounted = false;
    };
  }, [hasCategories, locale]);

  const parents = useMemo(() => groupCategoriesByParent(categories), [categories]);

  return {
    parents,
    isLoading,
  };
}
