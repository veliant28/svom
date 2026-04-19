"use client";

import type { HeaderCategorySection } from "@/shared/components/layout/header/categories/header-category.types";
import { SubcategorySection } from "@/shared/components/layout/header/categories/subcategory-section";

type FloatingSubcategoryGridProps = {
  sections: HeaderCategorySection[];
  activeCategoryKey: string | null;
  onNavigate: () => void;
};

export function FloatingSubcategoryGrid({ sections, activeCategoryKey, onNavigate }: FloatingSubcategoryGridProps) {
  return (
    <div className="grid grid-cols-1 gap-x-5 gap-y-6 sm:grid-cols-2 xl:grid-cols-3">
      {sections.map((section) => (
        <SubcategorySection
          key={section.id}
          title={section.title}
          items={section.items}
          activeCategoryKey={activeCategoryKey}
          onNavigate={onNavigate}
        />
      ))}
    </div>
  );
}
