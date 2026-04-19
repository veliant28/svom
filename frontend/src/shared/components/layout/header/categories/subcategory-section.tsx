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
        {items.map((category) => (
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
