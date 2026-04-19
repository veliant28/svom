import type { BackofficeSupplierPriceList } from "@/features/backoffice/types/suppliers.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function parseCsvStrings(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
    ),
  );
}

export function asNumberList(values: Array<number | string>): number[] {
  return Array.from(
    new Set(
      values
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0),
    ),
  );
}

export function asStringList(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter((value) => value.length > 0)));
}

export function resolveParamsSourceLabel(source: string | undefined, t: Translator): string {
  if (source === "utr_api") {
    return t("priceLifecycle.params.source.utr_api");
  }
  if (source === "gpl_api") {
    return t("priceLifecycle.params.source.gpl_api");
  }
  return t("priceLifecycle.params.source.fallback");
}

export function buildRequestPayloadFromRow({
  item,
  fallbackFormat,
}: {
  item: BackofficeSupplierPriceList;
  fallbackFormat: string;
}) {
  return {
    format: item.requested_format || fallbackFormat,
    in_stock: item.is_in_stock,
    show_scancode: item.supplier_code === "utr" ? item.show_scancode : false,
    utr_article: item.utr_article,
    visible_brands: asNumberList(item.visible_brands),
    categories: asStringList(item.categories),
    models_filter: asStringList(item.models_filter),
  };
}
