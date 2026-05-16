"use client";

import { Link } from "@/i18n/navigation";
import { buildCatalogCategoryHref } from "@/shared/components/layout/header/categories/category-navigation";

type SubcategoryTileProps = {
  categoryId: string;
  name: string;
  isActive: boolean;
  onNavigate: () => void;
  performanceMode?: "default" | "fast";
};

export function SubcategoryTile({ categoryId, name, isActive, onNavigate, performanceMode = "default" }: SubcategoryTileProps) {
  const href = buildCatalogCategoryHref(categoryId);
  const isFastMode = performanceMode === "fast";

  return (
    <Link
      href={href}
      scroll={false}
      onClick={onNavigate}
      className={`block rounded-lg border px-2.5 py-1.5 text-[13px] ${isFastMode ? "transition-colors duration-100" : "transition-all duration-150"}`}
      style={{
        borderColor: isActive ? "var(--accent)" : "color-mix(in srgb, var(--border) 85%, transparent)",
        backgroundColor: isActive
          ? "color-mix(in srgb, var(--accent) 10%, var(--surface))"
          : "color-mix(in srgb, var(--surface) 90%, #ffffff 10%)",
        boxShadow: isFastMode
          ? "none"
          : isActive
            ? "0 7px 16px rgba(228, 80, 31, 0.14)"
            : "0 4px 10px rgba(15, 23, 42, 0.07)",
      }}
    >
      <span className="line-clamp-1 block font-medium leading-tight">{name}</span>
    </Link>
  );
}
