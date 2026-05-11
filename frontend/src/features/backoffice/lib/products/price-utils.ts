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
  const summary = item.price_tooltip_summary;
  const finalPriceRaw = summary?.final_price || item.final_price || null;
  const selectedSupplierPriceRaw = summary?.selected_supplier_price || item.supplier_price || null;
  const utrPriceRaw = summary?.utr_price || null;
  const gplRrcPriceRaw = summary?.gpl_rrc_price || null;
  const markupRaw = summary?.markup_percent || item.applied_markup_percent || null;
  const appliedPolicyLabel = summary?.pricing_policy
    || (item.applied_markup_policy_scope === "global"
    ? t("products.tooltips.policyGlobal")
    : item.applied_markup_policy_scope === "category"
      ? t("products.tooltips.policyCategory")
      : item.applied_markup_policy_name || t("products.tooltips.notSet"));
  const priceUpdatedAt = summary?.updated_at || item.price_updated_at || item.updated_at;

  const displayPrice = formatProductPrice(finalPriceRaw, item.currency, locale);
  const supplierPrice = formatProductPrice(selectedSupplierPriceRaw, item.supplier_currency || item.currency, locale);
  const utrPrice = utrPriceRaw ? formatProductPrice(utrPriceRaw, item.supplier_currency || item.currency, locale) : "";
  const gplRrcPrice = gplRrcPriceRaw ? formatProductPrice(gplRrcPriceRaw, item.supplier_currency || item.currency, locale) : "";
  const badgeLabel = finalPriceRaw ? displayPrice : supplierPrice;
  const appliedMarkup = markupRaw ? `${markupRaw}%` : t("products.tooltips.notSet");

  return {
    displayPrice,
    badgeLabel,
    supplierPrice,
    utrPrice,
    gplRrcPrice,
    appliedMarkup,
    appliedPolicyLabel,
    priceUpdatedAtLabel: formatBackofficeDate(priceUpdatedAt),
    hasPolicy: Boolean(summary?.pricing_policy || item.applied_markup_policy_scope || item.applied_markup_policy_name),
  };
}
