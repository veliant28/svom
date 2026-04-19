"use client";

import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { useSearchSuggestions } from "@/features/search/hooks/use-search-suggestions";
import { SearchSuggestionsList } from "@/features/search/components/search/search-suggestions-list";
import type { CatalogProduct } from "@/features/catalog/types";

type SearchModalProps = {
  isOpen: boolean;
  onClose: () => void;
};

export function SearchModal({ isOpen, onClose }: SearchModalProps) {
  const t = useTranslations("common.header.searchModal");
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [isMounted, setIsMounted] = useState(false);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { suggestions, isLoading } = useSearchSuggestions({ query, enabled: isOpen });

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      inputRef.current?.focus();
    });

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen) {
      setQuery("");
    }
  }, [isOpen]);

  if (!isOpen || !isMounted) {
    return null;
  }

  function goToCatalogResults() {
    const normalized = query.trim();
    if (!normalized) {
      return;
    }
    router.push(`/catalog?q=${encodeURIComponent(normalized)}`);
    onClose();
  }

  function pickProduct(item: CatalogProduct) {
    router.push(`/catalog/${item.slug}`);
    onClose();
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[90] flex items-start justify-center bg-black/35 px-3 pb-6 pt-[12vh] backdrop-blur-[1px]"
      onMouseDown={(event) => {
        if (!dialogRef.current?.contains(event.target as Node)) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        className="w-full max-w-2xl rounded-2xl border p-4 shadow-2xl"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        role="dialog"
        aria-modal="true"
        aria-label={t("title")}
      >
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">{t("title")}</h2>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            aria-label={t("actions.close")}
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form
          className="mt-3"
          onSubmit={(event) => {
            event.preventDefault();
            goToCatalogResults();
          }}
        >
          <label
            className="flex h-12 items-center gap-2 rounded-xl border px-3 transition-colors focus-within:border-slate-500 focus-within:ring-2 focus-within:ring-slate-500/35"
            style={{ borderColor: "var(--border)" }}
          >
            <Search size={18} style={{ color: "var(--muted)" }} />
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("placeholder")}
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
        </form>

        <div className="mt-3 max-h-[52vh] overflow-y-auto pr-1">
          <SearchSuggestionsList
            query={query}
            suggestions={suggestions}
            isLoading={isLoading}
            onPickProduct={pickProduct}
          />
        </div>

        <div className="mt-3 flex justify-end">
          <button
            type="button"
            className="h-10 rounded-lg border px-4 text-sm font-medium disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={query.trim().length === 0}
            onClick={goToCatalogResults}
          >
            {t("actions.showAll")}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
