import { SupplierImportFilters } from "@/features/backoffice/components/supplier-import/supplier-import-filters";
import { SupplierImportQualityPanel } from "@/features/backoffice/components/supplier-import/supplier-import-quality-panel";
import type { UtrFilterMode } from "@/features/backoffice/lib/supplier-import/supplier-import-quality";
import type { BackofficeSupplierPriceListParams } from "@/features/backoffice/types/suppliers.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierImportActions({
  t,
  tokenReady,
  cooldownCanRun,
  supplierParams,
  format,
  formatOptions,
  inStockOnly,
  showScancode,
  utrArticle,
  onFormatChange,
  onInStockOnlyChange,
  onShowScancodeChange,
  onUtrArticleChange,
  onRequest,
  onDownload,
  onImport,
  canDownload,
  canImport,
  isUtr,
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
  selectedFiltersCount,
  activeCode,
  paramsSourceLabel,
}: {
  t: Translator;
  tokenReady: boolean;
  cooldownCanRun: boolean;
  supplierParams: BackofficeSupplierPriceListParams | null;
  format: string;
  formatOptions: Array<{ format: string; caption: string }>;
  inStockOnly: boolean;
  showScancode: boolean;
  utrArticle: boolean;
  onFormatChange: (value: string) => void;
  onInStockOnlyChange: (value: boolean) => void;
  onShowScancodeChange: (value: boolean) => void;
  onUtrArticleChange: (value: boolean) => void;
  onRequest: () => void;
  onDownload: () => void;
  onImport: () => void;
  canDownload: boolean;
  canImport: boolean;
  isUtr: boolean;
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
  selectedFiltersCount: number;
  activeCode: string;
  paramsSourceLabel: string;
}) {
  return (
    <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <h2 className="text-sm font-semibold">{t("priceLifecycle.operations.title")}</h2>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("priceLifecycle.operations.subtitle")}</p>

      <div className="mt-3 flex flex-wrap items-end gap-2">
        <button
          type="button"
          className="h-10 cursor-pointer rounded-md border px-4 text-sm font-semibold disabled:cursor-not-allowed"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          disabled={!tokenReady || !cooldownCanRun}
          onClick={onRequest}
        >
          {t("priceLifecycle.actions.request")}
        </button>

        <button
          type="button"
          className="h-10 cursor-pointer rounded-md border px-4 text-sm font-semibold disabled:cursor-not-allowed"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          disabled={!tokenReady || !canDownload}
          onClick={onDownload}
        >
          {t("priceLifecycle.actions.download")}
        </button>

        <button
          type="button"
          className="h-10 cursor-pointer rounded-md border px-4 text-sm font-semibold disabled:cursor-not-allowed"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          disabled={!tokenReady || !canImport}
          onClick={onImport}
        >
          {t("priceLifecycle.actions.import")}
        </button>

        <select
          value={format}
          onChange={(event) => onFormatChange(event.target.value)}
          aria-label={t("priceLifecycle.params.format")}
          title={t("priceLifecycle.params.format")}
          className="h-10 min-w-[12rem] cursor-pointer rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        >
          {formatOptions.map((itemFormat) => (
            <option key={itemFormat.format} value={itemFormat.format}>
              {itemFormat.caption || itemFormat.format}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {supplierParams?.supports?.in_stock ? (
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={inStockOnly}
              onChange={(event) => onInStockOnlyChange(event.target.checked)}
            />
            {t("priceLifecycle.params.inStockOnly")}
          </label>
        ) : null}
        {supplierParams?.supports?.show_scancode ? (
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={showScancode}
              onChange={(event) => onShowScancodeChange(event.target.checked)}
            />
            {t("priceLifecycle.params.showScancode")}
          </label>
        ) : null}
        {supplierParams?.supports?.utr_article ? (
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={utrArticle}
              onChange={(event) => onUtrArticleChange(event.target.checked)}
            />
            {t("priceLifecycle.params.utrArticle")}
          </label>
        ) : null}
      </div>

      <SupplierImportQualityPanel
        t={t}
        activeCode={activeCode}
        supplierParams={supplierParams}
        paramsSourceLabel={paramsSourceLabel}
      />

      <SupplierImportFilters
        t={t}
        isUtr={isUtr}
        supplierParams={supplierParams}
        utrFilterMode={utrFilterMode}
        onUtrFilterModeChange={onUtrFilterModeChange}
        selectedVisibleBrands={selectedVisibleBrands}
        selectedCategories={selectedCategories}
        selectedModels={selectedModels}
        manualModels={manualModels}
        onManualModelsChange={onManualModelsChange}
        onToggleVisibleBrand={onToggleVisibleBrand}
        onToggleCategory={onToggleCategory}
        onToggleModel={onToggleModel}
        selectedCount={selectedFiltersCount}
      />
    </article>
  );
}
