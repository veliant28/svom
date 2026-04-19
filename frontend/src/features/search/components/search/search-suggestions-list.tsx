"use client";

import { Search } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import type { CatalogProduct } from "@/features/catalog/types";

type SearchSuggestionsListProps = {
  query: string;
  suggestions: CatalogProduct[];
  isLoading: boolean;
  onPickProduct: (product: CatalogProduct) => void;
};

function formatPrice(value: string, currency: string, locale: string): string {
  const amount = Number(value);
  if (Number.isNaN(amount)) {
    return `${value} ${currency}`;
  }
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount) + ` ${currency}`;
}

export function SearchSuggestionsList({
  query,
  suggestions,
  isLoading,
  onPickProduct,
}: SearchSuggestionsListProps) {
  const t = useTranslations("common.header.searchModal");
  const locale = useLocale();

  if (query.trim().length < 2) {
    return (
      <p className="px-1 py-2 text-xs" style={{ color: "var(--muted)" }}>
        {t("states.minQuery")}
      </p>
    );
  }

  if (isLoading) {
    return (
      <p className="px-1 py-2 text-xs" style={{ color: "var(--muted)" }}>
        {t("states.loading")}
      </p>
    );
  }

  if (suggestions.length === 0) {
    return (
      <p className="px-1 py-2 text-xs" style={{ color: "var(--muted)" }}>
        {t("states.empty")}
      </p>
    );
  }

  return (
    <ul className="space-y-1">
      {suggestions.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            className="w-full rounded-lg border px-3 py-2 text-left transition-colors hover:bg-[color-mix(in_srgb,var(--surface-2)_64%,var(--surface))]"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => onPickProduct(item)}
          >
            <span className="inline-flex items-center gap-2 text-sm font-medium">
              <Search size={14} />
              <span className="line-clamp-1">{item.name}</span>
            </span>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
              {item.brand.name} · {item.article || item.sku}
            </p>
            <p className="mt-1 text-xs font-semibold">{formatPrice(item.final_price, item.currency, locale)}</p>
          </button>
        </li>
      ))}
    </ul>
  );
}
