"use client";

import { LoaderCircle, ShoppingBag } from "lucide-react";
import type { RefObject } from "react";
import type { KeyboardEvent } from "react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { buildCompactCategoryLabel } from "@/features/backoffice/lib/integration-center.config";
import type { BackofficeReturnsSettingsState, IntegrationCenterToggleKey } from "@/features/backoffice/types/integration-center.types";
import type { CheckoutNovaPoshtaSettlement, CheckoutNovaPoshtaWarehouse } from "@/features/checkout/api/lookup-nova-poshta";
import { formatWarehouseInputValue } from "@/features/checkout/lib/checkout-page.helpers";

type ReturnsField =
  | "returns_recipient_full_name"
  | "returns_recipient_phone"
  | "returns_city_ref"
  | "returns_city_label"
  | "returns_np_warehouse_text";

type ReturnCategoryOption = {
  id: string;
  label: string;
};

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ReturnsSettingsCard({
  t,
  state,
  updatingKeys,
  returnsSettings,
  returnsPhoneInput,
  returnsSettlementQuery,
  returnsWarehouseQuery,
  returnsSettlementOptions,
  returnsWarehouseOptions,
  isReturnsSettlementLoading,
  isReturnsWarehouseLoading,
  isReturnsSettlementOpen,
  isReturnsWarehouseOpen,
  returnsSettlementActiveIndex,
  returnsWarehouseActiveIndex,
  settlementDropdownRef,
  warehouseDropdownRef,
  returnsSettlementScope,
  returnsWarehouseScope,
  returnsCategorySearch,
  returnsCategorySuggestions,
  categoryOptionById,
  isUpdatingReturnsCategories,
  onToggle,
  setReturnsSettings,
  onReturnsFieldCommit,
  onReturnsPhoneInputChange,
  onReturnsPhoneCommit,
  onSettlementQueryChange,
  onSettlementOpen,
  onSettlementBlur,
  onSettlementKeyDown,
  onSettlementHoverIndex,
  onSettlementSelect,
  onWarehouseQueryChange,
  onWarehouseOpen,
  onWarehouseBlur,
  onWarehouseKeyDown,
  onWarehouseHoverIndex,
  onWarehouseSelect,
  onCategorySearchChange,
  onCategoryKeyDown,
  onCategoryAdd,
  onCategoryRemove,
}: {
  t: Translator;
  state: Record<string, boolean> | null;
  updatingKeys: Record<string, boolean>;
  returnsSettings: BackofficeReturnsSettingsState | null;
  returnsPhoneInput: string;
  returnsSettlementQuery: string;
  returnsWarehouseQuery: string;
  returnsSettlementOptions: CheckoutNovaPoshtaSettlement[];
  returnsWarehouseOptions: CheckoutNovaPoshtaWarehouse[];
  isReturnsSettlementLoading: boolean;
  isReturnsWarehouseLoading: boolean;
  isReturnsSettlementOpen: boolean;
  isReturnsWarehouseOpen: boolean;
  returnsSettlementActiveIndex: number;
  returnsWarehouseActiveIndex: number;
  settlementDropdownRef: RefObject<HTMLDivElement | null>;
  warehouseDropdownRef: RefObject<HTMLDivElement | null>;
  returnsSettlementScope: string;
  returnsWarehouseScope: string;
  returnsCategorySearch: string;
  returnsCategorySuggestions: ReturnCategoryOption[];
  categoryOptionById: Record<string, ReturnCategoryOption>;
  isUpdatingReturnsCategories: boolean;
  onToggle: (key: IntegrationCenterToggleKey, enabled: boolean) => void;
  setReturnsSettings: (updater: (prev: BackofficeReturnsSettingsState | null) => BackofficeReturnsSettingsState | null) => void;
  onReturnsFieldCommit: (field: ReturnsField, value: string) => void;
  onReturnsPhoneInputChange: (value: string) => void;
  onReturnsPhoneCommit: () => void;
  onSettlementQueryChange: (value: string) => void;
  onSettlementOpen: () => void;
  onSettlementBlur: (value: string) => void;
  onSettlementKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onSettlementHoverIndex: (index: number) => void;
  onSettlementSelect: (row: CheckoutNovaPoshtaSettlement) => void;
  onWarehouseQueryChange: (value: string) => void;
  onWarehouseOpen: () => void;
  onWarehouseBlur: (value: string) => void;
  onWarehouseKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onWarehouseHoverIndex: (index: number) => void;
  onWarehouseSelect: (row: CheckoutNovaPoshtaWarehouse) => void;
  onCategorySearchChange: (value: string) => void;
  onCategoryKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onCategoryAdd: (categoryId: string) => void;
  onCategoryRemove: (categoryId: string) => void;
}) {
  return (
    <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
        <ShoppingBag size={16} />
        <span>{t("integrationCenter.returns.title")}</span>
      </p>
      <div className="grid gap-3 xl:grid-cols-3">
        <div className="grid gap-2 xl:col-span-1">
          <BackofficeTooltip content={t("integrationCenter.returns.enabledHint")} placement="top" align="center" wrapperClassName="block">
            <button
              type="button"
              aria-pressed={Boolean(state?.["returns.enabled"])}
              disabled={Boolean(updatingKeys["returns.enabled"])}
              className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-md border px-2.5 py-2 text-left text-xs disabled:opacity-80"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              onClick={() => {
                onToggle("returns.enabled", !Boolean(state?.["returns.enabled"]));
              }}
            >
              <span>{t("integrationCenter.returns.enabledLabel")}</span>
              <span className="inline-flex items-center gap-2">
                {updatingKeys["returns.enabled"] ? <LoaderCircle size={14} className="animate-spin" /> : null}
                <input type="checkbox" checked={Boolean(state?.["returns.enabled"])} readOnly tabIndex={-1} className="pointer-events-none h-4 w-4" />
              </span>
            </button>
          </BackofficeTooltip>

          <label className="grid gap-1 text-xs">
            <span>{t("integrationCenter.returns.fields.recipientFullName")}</span>
            <input
              type="text"
              value={returnsSettings?.returns_recipient_full_name || ""}
              onChange={(event) => setReturnsSettings((prev) => (prev ? { ...prev, returns_recipient_full_name: event.target.value } : prev))}
              onBlur={(event) => { onReturnsFieldCommit("returns_recipient_full_name", event.target.value); }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onReturnsFieldCommit("returns_recipient_full_name", event.currentTarget.value);
                }
              }}
              className="h-9 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
          </label>

          <label className="grid gap-1 text-xs">
            <span>{t("integrationCenter.returns.fields.recipientPhone")}</span>
            <input
              type="tel"
              value={returnsPhoneInput}
              onChange={(event) => onReturnsPhoneInputChange(event.target.value)}
              onBlur={onReturnsPhoneCommit}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onReturnsPhoneCommit();
                }
              }}
              placeholder={t("integrationCenter.returns.placeholders.recipientPhone")}
              className="h-9 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
          </label>

          <label className="relative grid gap-1 text-xs">
            <span>{t("integrationCenter.returns.fields.settlementLabel")}</span>
            <input
              type="text"
              value={returnsSettlementQuery}
              onChange={(event) => onSettlementQueryChange(event.target.value)}
              onFocus={onSettlementOpen}
              onBlur={(event) => onSettlementBlur(event.target.value)}
              onKeyDown={onSettlementKeyDown}
              placeholder={t("integrationCenter.returns.placeholders.settlementLabel")}
              className="h-9 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
            {isReturnsSettlementLoading ? <LoaderCircle size={14} className="absolute right-2 top-8 animate-spin" /> : null}
            {isReturnsSettlementOpen && returnsSettlementOptions.length ? (
              <div ref={settlementDropdownRef} className="absolute top-[58px] z-20 max-h-56 w-full overflow-y-auto rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                {returnsSettlementOptions.map((row, index) => (
                  <button
                    key={`${row.delivery_city_ref || row.ref}:${row.label}`}
                    type="button"
                    className="block w-full border-b px-2 py-1.5 text-left text-xs last:border-b-0"
                    style={{
                      borderColor: "var(--border)",
                      backgroundColor: index === returnsSettlementActiveIndex ? "var(--surface-2)" : "transparent",
                    }}
                    data-nav-scope={returnsSettlementScope}
                    data-nav-index={index}
                    onMouseDown={(event) => { event.preventDefault(); }}
                    onMouseEnter={() => { onSettlementHoverIndex(index); }}
                    onClick={() => { onSettlementSelect(row); }}
                  >
                    <span className="block">{row.label}</span>
                    <span style={{ color: "var(--muted)" }}>{String(row.area || row.region || "").trim()}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </label>

          <label className="relative grid gap-1 text-xs">
            <span>{t("integrationCenter.returns.fields.warehouseLookupLabel")}</span>
            <input
              type="text"
              value={returnsWarehouseQuery}
              onChange={(event) => onWarehouseQueryChange(event.target.value)}
              onFocus={onWarehouseOpen}
              onBlur={(event) => onWarehouseBlur(event.target.value)}
              onKeyDown={onWarehouseKeyDown}
              placeholder={t("integrationCenter.returns.placeholders.warehouseLookupLabel")}
              className="h-9 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
            {isReturnsWarehouseLoading ? <LoaderCircle size={14} className="absolute right-2 top-8 animate-spin" /> : null}
            {isReturnsWarehouseOpen && returnsWarehouseOptions.length ? (
              <div ref={warehouseDropdownRef} className="absolute bottom-[58px] z-20 max-h-56 w-full overflow-y-auto rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                {returnsWarehouseOptions.map((row, index) => (
                  <button
                    key={`${row.ref}:${row.number}`}
                    type="button"
                    className="block w-full border-b px-2 py-1.5 text-left text-xs last:border-b-0"
                    style={{
                      borderColor: "var(--border)",
                      backgroundColor: index === returnsWarehouseActiveIndex ? "var(--surface-2)" : "transparent",
                    }}
                    data-nav-scope={returnsWarehouseScope}
                    data-nav-index={index}
                    onMouseDown={(event) => { event.preventDefault(); }}
                    onMouseEnter={() => { onWarehouseHoverIndex(index); }}
                    onClick={() => { onWarehouseSelect(row); }}
                  >
                    {formatWarehouseInputValue(row, "uk")}
                  </button>
                ))}
              </div>
            ) : null}
          </label>
        </div>

        <div className="grid gap-3 xl:col-span-2">
          <div className="mt-1 grid gap-2">
            <p className="text-xs font-semibold">{t("integrationCenter.returns.nonReturnableTitle")}</p>
            <div className="flex flex-wrap gap-2">
              {(returnsSettings?.returns_non_returnable_category_ids || []).map((categoryId) => (
                <span key={categoryId} className="inline-flex items-center gap-2 rounded-md border px-2 py-1 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <span>
                    {(() => {
                      const compactLabel = buildCompactCategoryLabel(categoryOptionById[categoryId]?.label || categoryId);
                      return returnsSettings?.returns_include_subcategories
                        ? `${compactLabel}+${t("integrationCenter.returns.includeSubcategoriesSuffix")}`
                        : compactLabel;
                    })()}
                  </span>
                  <button
                    type="button"
                    className="inline-flex h-5 w-5 items-center justify-center rounded-md border"
                    style={{ borderColor: "var(--border)" }}
                    onClick={() => {
                      onCategoryRemove(categoryId);
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>

            <div className="relative grid gap-2">
              <input
                type="text"
                value={returnsCategorySearch}
                onChange={(event) => onCategorySearchChange(event.target.value)}
                placeholder={t("integrationCenter.returns.nonReturnablePlaceholder")}
                className="h-9 rounded-md border px-2 text-xs"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                onKeyDown={onCategoryKeyDown}
              />
              {returnsCategorySuggestions.length ? (
                <div className="max-h-56 overflow-y-auto rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  {returnsCategorySuggestions.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      className="flex w-full items-center justify-between border-b px-2 py-1.5 text-left text-xs last:border-b-0"
                      style={{ borderColor: "var(--border)" }}
                      onClick={() => {
                        onCategoryAdd(option.id);
                      }}
                      disabled={isUpdatingReturnsCategories}
                    >
                      <span className="line-clamp-2">{option.label}</span>
                      <span className="inline-flex h-6 items-center rounded-md border px-2 text-[11px] font-semibold" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                        {t("integrationCenter.returns.addCategory")}
                      </span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
