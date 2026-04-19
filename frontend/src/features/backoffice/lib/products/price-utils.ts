import type { BackofficeCatalogProduct } from "@/features/backoffice/types/catalog.types";

import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";

import { formatProductPrice } from "./product-formatters";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function buildProductPriceMeta({
  item,
  locale,
  t,
}: {
  item: BackofficeCatalogProduct;
  locale: string;
  t: Translator;
}) {
  const displayPrice = formatProductPrice(item.final_price, item.currency, locale);
  const supplierPrice = item.supplier_price
    ? formatProductPrice(item.supplier_price, item.supplier_currency || item.currency, locale)
    : "-";
  const appliedMarkup = item.applied_markup_percent ? `${item.applied_markup_percent}%` : t("products.tooltips.notSet");
  const appliedPolicyLabel = item.applied_markup_policy_scope === "global"
    ? t("products.tooltips.policyGlobal")
    : item.applied_markup_policy_scope === "category"
      ? t("products.tooltips.policyCategory")
      : item.applied_markup_policy_name || t("products.tooltips.notSet");
  const priceUpdatedAt = item.price_updated_at || item.updated_at;

  return {
    displayPrice,
    supplierPrice,
    appliedMarkup,
    appliedPolicyLabel,
    priceUpdatedAtLabel: formatBackofficeDate(priceUpdatedAt),
    hasPolicy: Boolean(item.applied_markup_policy_scope || item.applied_markup_policy_name),
  };
}
