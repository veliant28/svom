import type { HeaderCategoryParent, HeaderCategorySection } from "./header-category.types";

type HeaderCategoryInput = {
  id: string;
  name: string;
  slug: string;
  sort_order?: number;
  parent?: {
    id: string;
    name: string;
    slug: string;
    sort_order?: number;
  } | null | undefined;
};

export const HEADER_MAX_PARENT_ITEMS = 10;

function normalizeHeaderCategoryLabel(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function byOrderThenName(left: HeaderCategoryInput, right: HeaderCategoryInput): number {
  const leftOrder = Number.isFinite(left.sort_order) ? Number(left.sort_order) : 1000;
  const rightOrder = Number.isFinite(right.sort_order) ? Number(right.sort_order) : 1000;
  if (leftOrder !== rightOrder) {
    return leftOrder - rightOrder;
  }
  return left.name.localeCompare(right.name);
}

function dedupeCategories(categories: HeaderCategoryInput[]): HeaderCategoryInput[] {
  const out: HeaderCategoryInput[] = [];
  const seen = new Set<string>();
  for (const category of categories) {
    const id = String(category.id || "").trim();
    const slug = String(category.slug || "").trim();
    const name = String(category.name || "").trim();
    if (!id || !slug || !name) {
      continue;
    }
    const key = `${id}:${slug}:${normalizeHeaderCategoryLabel(name)}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    out.push(category);
  }
  return out;
}

export function groupHeaderCategories(categories: HeaderCategoryInput[]): HeaderCategoryParent[] {
  const normalizedInput = dedupeCategories(categories);
  const childrenByParentId = new Map<string, HeaderCategoryInput[]>();

  normalizedInput.forEach((category) => {
    if (!category.parent) {
      return;
    }
    const bucket = childrenByParentId.get(category.parent.id) ?? [];
    bucket.push(category);
    childrenByParentId.set(category.parent.id, bucket);
  });

  function collectDescendantNodes(categoryId: string): HeaderCategoryInput[] {
    const children = [...(childrenByParentId.get(categoryId) ?? [])].sort(byOrderThenName);
    if (children.length === 0) {
      return [];
    }

    return children.flatMap((child) => [child, ...collectDescendantNodes(child.id)]);
  }

  const roots = normalizedInput
    .filter((category) => !category.parent)
    .sort(byOrderThenName);

  const dedupedRoots: HeaderCategoryInput[] = [];
  const seenRootLabels = new Set<string>();
  for (const root of roots) {
    const marker = normalizeHeaderCategoryLabel(root.name);
    if (!marker || seenRootLabels.has(marker)) {
      continue;
    }
    seenRootLabels.add(marker);
    dedupedRoots.push(root);
    if (dedupedRoots.length >= HEADER_MAX_PARENT_ITEMS) {
      break;
    }
  }

  return dedupedRoots.map((root) => {
    const directChildren = [...(childrenByParentId.get(root.id) ?? [])].sort(byOrderThenName);

    const directLeafs: HeaderCategoryInput[] = [];
    const groupedSections: HeaderCategorySection[] = [];

    directChildren.forEach((child) => {
      const descendants = collectDescendantNodes(child.id);
      if (descendants.length === 0) {
        directLeafs.push(child);
        return;
      }
      const dedupedDescendants = dedupeCategories(descendants);
      if (dedupedDescendants.length === 0) {
        return;
      }
      const childLabel = normalizeHeaderCategoryLabel(child.name);
      const seenLabels = new Set<string>();
      const visibleItems = dedupedDescendants.filter((item) => {
        const label = normalizeHeaderCategoryLabel(item.name);
        if (!label) {
          return false;
        }
        if (label === childLabel) {
          return false;
        }
        if (seenLabels.has(label)) {
          return false;
        }
        seenLabels.add(label);
        return true;
      });
      if (visibleItems.length === 0) {
        return;
      }

      groupedSections.push({
        id: `${root.id}-${child.id}`,
        title: child.name,
        items: visibleItems,
      });
    });

    const sections: HeaderCategorySection[] = [];
    sections.push(...groupedSections);

    if (directLeafs.length > 0) {
      sections.push({
        id: `${root.id}-direct`,
        title: null,
        items: dedupeCategories(directLeafs),
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
