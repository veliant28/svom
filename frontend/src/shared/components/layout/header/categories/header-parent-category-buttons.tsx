"use client";

import { useMemo, useState } from "react";

import { CategoryModal } from "@/shared/components/layout/header/categories/category-modal";
import { CategoryParentIcon } from "@/shared/components/layout/header/categories/category-icon-mapping";
import type { HeaderCategoryParent } from "@/shared/components/layout/header/categories/header-category.types";
import { useHeaderCategoryGroups } from "@/shared/components/layout/header/categories/use-header-category-groups";
import { HeaderIconButton } from "@/shared/components/layout/header/header-icon-control";
import type { CategorySummary } from "@/features/catalog/types";

export function HeaderParentCategoryButtons({ initialCategories = [] }: { initialCategories?: CategorySummary[] }) {
  const { parents, isLoading } = useHeaderCategoryGroups(initialCategories);
  const [openParentId, setOpenParentId] = useState<string | null>(null);

  const activeParent = useMemo<HeaderCategoryParent | null>(
    () => parents.find((parent) => parent.id === openParentId) ?? null,
    [openParentId, parents],
  );

  if (isLoading || parents.length === 0) {
    return null;
  }

  return (
    <>
      <div className="flex items-center gap-2">
        {parents.map((parent) => (
          <HeaderIconButton
            key={parent.id}
            tooltip={parent.name}
            ariaLabel={parent.name}
            icon={<CategoryParentIcon slug={parent.slug} name={parent.name} size={34} />}
            onClick={() => setOpenParentId(parent.id)}
            isActive={activeParent?.id === parent.id}
            className="header-control-category"
          />
        ))}
      </div>

      <CategoryModal
        parent={activeParent}
        isOpen={Boolean(activeParent)}
        onClose={() => setOpenParentId(null)}
      />
    </>
  );
}
