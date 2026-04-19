import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

import { getCategoryDisplayName } from "./category-formatters";

export function buildCategoryLineage({
  category,
  parentById,
  locale,
}: {
  category: BackofficeCatalogCategory;
  parentById: Record<string, BackofficeCatalogCategory>;
  locale: string;
}): string[] {
  const lineage: string[] = [];
  const visited = new Set<string>();
  let current: BackofficeCatalogCategory | null = category;

  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    lineage.unshift(getCategoryDisplayName(current, locale));
    if (!current.parent) {
      break;
    }

    const parentCategory: BackofficeCatalogCategory | undefined = parentById[current.parent];
    if (!parentCategory) {
      if (current.parent_name) {
        lineage.unshift(current.parent_name);
      }
      break;
    }
    current = parentCategory;
  }

  return lineage;
}

export function getCategoryParentOptionLabel({
  category,
  parentById,
  locale,
}: {
  category: BackofficeCatalogCategory;
  parentById: Record<string, BackofficeCatalogCategory>;
  locale: string;
}): string {
  const lineage = buildCategoryLineage({ category, parentById, locale });
  const depth = Math.max(lineage.length - 1, 0);
  const treePrefix = depth > 0 ? `${"|    ".repeat(Math.max(0, depth - 1))}|---- ` : "";
  return `${treePrefix}${getCategoryDisplayName(category, locale)}`;
}

export function sortCategoryParentOptions({
  categories,
  parentById,
  locale,
}: {
  categories: BackofficeCatalogCategory[];
  parentById: Record<string, BackofficeCatalogCategory>;
  locale: string;
}): BackofficeCatalogCategory[] {
  const withKeys = categories.map((item) => {
    const lineage = buildCategoryLineage({ category: item, parentById, locale });
    return {
      item,
      sortKey: (lineage.length ? lineage.join(" > ") : getCategoryDisplayName(item, locale)).toLowerCase(),
    };
  });

  withKeys.sort((a, b) => a.sortKey.localeCompare(b.sortKey, locale));
  return withKeys.map((entry) => entry.item);
}

export function buildChildIdsByParentId(categories: BackofficeCatalogCategory[]): Record<string, string[]> {
  return categories.reduce<Record<string, string[]>>((acc, item) => {
    if (!item.parent) {
      return acc;
    }
    if (!acc[item.parent]) {
      acc[item.parent] = [];
    }
    acc[item.parent].push(item.id);
    return acc;
  }, {});
}

export function buildDisabledParentIds({
  editingCategoryId,
  childIdsByParentId,
}: {
  editingCategoryId: string | null;
  childIdsByParentId: Record<string, string[]>;
}): Set<string> {
  const ids = new Set<string>();
  if (!editingCategoryId) {
    return ids;
  }

  ids.add(editingCategoryId);
  const queue: string[] = [editingCategoryId];

  while (queue.length > 0) {
    const currentId = queue.shift();
    if (!currentId) {
      continue;
    }

    const children = childIdsByParentId[currentId] ?? [];
    for (const childId of children) {
      if (ids.has(childId)) {
        continue;
      }
      ids.add(childId);
      queue.push(childId);
    }
  }

  return ids;
}
