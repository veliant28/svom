"use client";

import type { CategorySummary } from "@/features/catalog/types";
import { SubcategoryTile } from "@/shared/components/layout/header/categories/subcategory-tile";

type SubcategorySectionProps = {
  title: string | null;
  items: CategorySummary[];
  activeCategoryKey: string | null;
  onNavigate: () => void;
};

export function SubcategorySection({ title, items, activeCategoryKey, onNavigate }: SubcategorySectionProps) {
  const normalize = (value: string) => value.trim().replace(/\s+/g, " ").toLocaleLowerCase();
  const normalizedTitle = title ? normalize(title) : "";
  const seenItemLabels = new Set<string>();
  const visibleItems = items.filter((category) => {
    const marker = normalize(category.name);
    if (!marker) {
      return false;
    }
    if (marker === normalizedTitle) {
      return false;
    }
    if (seenItemLabels.has(marker)) {
      return false;
    }
    seenItemLabels.add(marker);
    return true;
  });

  return (
    <section className="min-w-0">
      {title ? (
        <p
          className="mb-2 text-xs font-semibold uppercase tracking-[0.06em]"
          style={{ color: "color-mix(in srgb, var(--muted) 88%, var(--text))" }}
        >
          {title}
        </p>
      ) : null}

      <div className="space-y-1.5">
        {visibleItems.map((category) => (
          <div key={category.id}>
            <SubcategoryTile
              categoryId={category.id}
              name={category.name}
              isActive={activeCategoryKey === category.id || activeCategoryKey === category.slug}
              onNavigate={onNavigate}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
