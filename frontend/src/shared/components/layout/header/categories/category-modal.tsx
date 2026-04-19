"use client";

import { X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";

import { CategoryParentIcon } from "@/shared/components/layout/header/categories/category-icon-mapping";
import { FloatingSubcategoryGrid } from "@/shared/components/layout/header/categories/floating-subcategory-grid";
import type { HeaderCategoryParent } from "@/shared/components/layout/header/categories/header-category.types";
import { useActiveCatalogCategoryKey } from "@/shared/components/layout/header/categories/category-navigation";

type CategoryModalProps = {
  parent: HeaderCategoryParent | null;
  isOpen: boolean;
  onClose: () => void;
};

export function CategoryModal({ parent, isOpen, onClose }: CategoryModalProps) {
  const t = useTranslations("common.header.categoryModal");
  const activeCategoryKey = useActiveCatalogCategoryKey();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen, onClose]);

  const sections = useMemo(() => parent?.sections ?? [], [parent?.sections]);

  if (!isMounted || !isOpen || !parent) {
    return null;
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[95] flex items-start justify-center bg-black/35 px-3 pb-6 pt-[10vh] backdrop-blur-[1px]"
      onMouseDown={(event) => {
        if (!dialogRef.current?.contains(event.target as Node)) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        className="w-full max-w-7xl rounded-2xl border p-6 shadow-2xl"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        role="dialog"
        aria-modal="true"
        aria-label={parent.name}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border"
              style={{
                borderColor: "color-mix(in srgb, var(--accent) 40%, var(--border))",
                backgroundColor: "color-mix(in srgb, var(--accent) 10%, var(--surface))",
              }}
            >
              <CategoryParentIcon slug={parent.slug} name={parent.name} size={34} />
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold">{parent.name}</h2>
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                {t("subtitle")}
              </p>
            </div>
          </div>

          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={onClose}
            aria-label={t("actions.close")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-5 max-h-[70vh] overflow-y-auto pr-1">
          {sections.length > 0 ? (
            <FloatingSubcategoryGrid
              sections={sections}
              activeCategoryKey={activeCategoryKey}
              onNavigate={onClose}
            />
          ) : (
            <div
              className="rounded-xl border px-3 py-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "color-mix(in srgb, var(--surface-2) 55%, var(--surface))" }}
            >
              <p style={{ color: "var(--muted)" }}>{t("states.empty")}</p>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
