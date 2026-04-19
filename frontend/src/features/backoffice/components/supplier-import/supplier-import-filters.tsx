import { SUPPLIER_IMPORT_CHIP_BACKGROUND, type UtrFilterMode } from "@/features/backoffice/lib/supplier-import/supplier-import-quality";
import type { BackofficeSupplierPriceListParams } from "@/features/backoffice/types/suppliers.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierImportFilters({
  t,
  isUtr,
  supplierParams,
  utrFilterMode,
  onUtrFilterModeChange,
  selectedVisibleBrands,
  selectedCategories,
  selectedModels,
  manualModels,
  onManualModelsChange,
  onToggleVisibleBrand,
  onToggleCategory,
  onToggleModel,
  selectedCount,
}: {
  t: Translator;
  isUtr: boolean;
  supplierParams: BackofficeSupplierPriceListParams | null;
  utrFilterMode: UtrFilterMode;
  onUtrFilterModeChange: (value: UtrFilterMode) => void;
  selectedVisibleBrands: number[];
  selectedCategories: string[];
  selectedModels: string[];
  manualModels: string;
  onManualModelsChange: (value: string) => void;
  onToggleVisibleBrand: (id: number) => void;
  onToggleCategory: (id: string) => void;
  onToggleModel: (name: string) => void;
  selectedCount: number;
}) {
  if (!isUtr || supplierParams?.source !== "utr_api") {
    return null;
  }

  return (
    <div className="mt-3 rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <div className="grid gap-2 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center">
        <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.params.filterMode")}</p>
        <select
          value={utrFilterMode}
          onChange={(event) => onUtrFilterModeChange(event.target.value as UtrFilterMode)}
          className="h-9 rounded-md border px-2 text-xs"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="all">{t("priceLifecycle.params.filterNone")}</option>
          <option value="brands">{t("priceLifecycle.params.filterBrands")}</option>
          <option value="categories">{t("priceLifecycle.params.filterCategories")}</option>
          <option value="models">{t("priceLifecycle.params.filterModels")}</option>
        </select>
      </div>

      {utrFilterMode === "brands" ? (
        <div className="mt-3 space-y-2">
          <div className="flex max-h-36 flex-wrap gap-1 overflow-auto rounded-md border p-2" style={{ borderColor: "var(--border)" }}>
            {(supplierParams.visible_brands ?? []).map((item) => {
              const id = Number(item.id);
              if (!Number.isFinite(id) || id <= 0) {
                return null;
              }
              const isActive = selectedVisibleBrands.includes(id);
              return (
                <button
                  key={`brand-${id}`}
                  type="button"
                  className="cursor-pointer rounded-full border px-2 py-1 text-[11px] font-semibold"
                  style={{
                    borderColor: "var(--border)",
                    backgroundColor: isActive ? SUPPLIER_IMPORT_CHIP_BACKGROUND[0] : "var(--surface)",
                  }}
                  onClick={() => onToggleVisibleBrand(id)}
                  title={`#${id} ${item.title}`}
                >
                  {item.title || `#${id}`}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {utrFilterMode === "categories" ? (
        <div className="mt-3 space-y-2">
          <div className="flex max-h-36 flex-wrap gap-1 overflow-auto rounded-md border p-2" style={{ borderColor: "var(--border)" }}>
            {(supplierParams.categories ?? []).map((item) => {
              const id = item.id?.trim();
              if (!id) {
                return null;
              }
              const isActive = selectedCategories.includes(id);
              return (
                <button
                  key={`category-${id}`}
                  type="button"
                  className="cursor-pointer rounded-full border px-2 py-1 text-[11px] font-semibold"
                  style={{
                    borderColor: "var(--border)",
                    backgroundColor: isActive ? SUPPLIER_IMPORT_CHIP_BACKGROUND[1] : "var(--surface)",
                  }}
                  onClick={() => onToggleCategory(id)}
                  title={`${id} ${item.title}`}
                >
                  {item.title || id}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {utrFilterMode === "models" ? (
        <div className="mt-3 space-y-2">
          <div className="flex max-h-36 flex-wrap gap-1 overflow-auto rounded-md border p-2" style={{ borderColor: "var(--border)" }}>
            {(supplierParams.models ?? []).map((item) => {
              const name = item.name?.trim();
              if (!name) {
                return null;
              }
              const isActive = selectedModels.includes(name);
              return (
                <button
                  key={`model-${name}`}
                  type="button"
                  className="cursor-pointer rounded-full border px-2 py-1 text-[11px] font-semibold"
                  style={{
                    borderColor: "var(--border)",
                    backgroundColor: isActive ? SUPPLIER_IMPORT_CHIP_BACKGROUND[2] : "var(--surface)",
                  }}
                  onClick={() => onToggleModel(name)}
                  title={name}
                >
                  {name}
                </button>
              );
            })}
          </div>
          <input
            value={manualModels}
            onChange={(event) => onManualModelsChange(event.target.value)}
            placeholder={t("priceLifecycle.params.manualPlaceholderModels")}
            className="h-9 w-full rounded-md border px-2 text-xs"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </div>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium" style={{ color: "var(--muted)" }}>
          {t("priceLifecycle.params.filterOneOfRule")}
        </p>
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          {t("priceLifecycle.params.selectedCount", { count: selectedCount })}
        </p>
      </div>

      {(supplierParams.visible_brands_truncated || supplierParams.categories_truncated || supplierParams.models_truncated) ? (
        <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
          {t("priceLifecycle.params.truncatedHint")}
        </p>
      ) : null}
    </div>
  );
}
