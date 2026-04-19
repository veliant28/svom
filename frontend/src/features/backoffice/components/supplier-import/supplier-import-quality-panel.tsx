import type { BackofficeSupplierPriceListParams } from "@/features/backoffice/types/suppliers.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierImportQualityPanel({
  t,
  activeCode,
  supplierParams,
  paramsSourceLabel,
}: {
  t: Translator;
  activeCode: string;
  supplierParams: BackofficeSupplierPriceListParams | null;
  paramsSourceLabel: string;
}) {
  return (
    <>
      <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
        {paramsSourceLabel}
      </p>

      {supplierParams?.source === "utr_api" ? (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          {t("priceLifecycle.params.dynamicHint", {
            brands: supplierParams.visible_brands_count,
            categories: supplierParams.categories_count,
            models: supplierParams.models_count,
          })}
        </p>
      ) : null}

      <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>
        {activeCode === "utr"
          ? t("priceLifecycle.notes.utrGeneration")
          : t("priceLifecycle.notes.gplReady")}
      </p>
    </>
  );
}
