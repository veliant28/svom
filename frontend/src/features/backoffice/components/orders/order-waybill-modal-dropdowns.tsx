import { createPortal } from "react-dom";
import type { CSSProperties, RefObject } from "react";

import type {
  Translator,
  WaybillAddressSuggestion,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import { resolveCounterpartyTypeDisplay } from "@/features/backoffice/components/orders/order-waybill-party.helpers";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupPackaging,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
} from "@/features/backoffice/types/nova-poshta.types";

type DropdownStyle = CSSProperties | null;

type DropdownRef = RefObject<HTMLDivElement | null>;

function portalIsAvailable() {
  return typeof document !== "undefined";
}

export function CityDropdownPortal({
  dropdownRef,
  dropdownStyle,
  loading,
  rows,
  activeIndex,
  t,
  onActiveIndexChange,
  onSelect,
}: {
  dropdownRef: DropdownRef;
  dropdownStyle: DropdownStyle;
  loading: boolean;
  rows: BackofficeNovaPoshtaLookupSettlement[];
  activeIndex: number;
  t: Translator;
  onActiveIndexChange: (index: number) => void;
  onSelect: (row: BackofficeNovaPoshtaLookupSettlement) => void;
}) {
  if (!portalIsAvailable() || !dropdownStyle) {
    return null;
  }

  return createPortal(
    <div
      ref={dropdownRef}
      className="rounded-md border"
      style={{ ...dropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
      role="listbox"
      aria-label={t("orders.modals.waybill.fields.city")}
    >
      {loading ? (
        <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
      ) : rows.map((row, index) => (
        <button
          key={`${row.ref}:${row.label}`}
          type="button"
          data-nav-scope="waybill-city"
          data-nav-index={index}
          className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
          style={{
            borderColor: "var(--border)",
            backgroundColor: index === activeIndex ? "var(--surface-2)" : "var(--surface)",
          }}
          role="option"
          aria-selected={index === activeIndex}
          onMouseEnter={() => onActiveIndexChange(index)}
          onClick={() => onSelect(row)}
        >
          {row.label}
        </button>
      ))}
    </div>,
    document.body,
  );
}

export function RecipientCounterpartyDropdownPortal({
  dropdownRef,
  dropdownStyle,
  loading,
  rows,
  activeIndex,
  t,
  onActiveIndexChange,
  onSelect,
}: {
  dropdownRef: DropdownRef;
  dropdownStyle: DropdownStyle;
  loading: boolean;
  rows: BackofficeNovaPoshtaLookupCounterparty[];
  activeIndex: number;
  t: Translator;
  onActiveIndexChange: (index: number) => void;
  onSelect: (row: BackofficeNovaPoshtaLookupCounterparty) => void;
}) {
  if (!portalIsAvailable() || !dropdownStyle) {
    return null;
  }

  return createPortal(
    <div
      ref={dropdownRef}
      className="rounded-md border"
      style={{ ...dropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
      role="listbox"
      aria-label={t("orders.modals.waybill.fields.counterparty")}
    >
      {loading ? (
        <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
      ) : rows.map((row, index) => {
        const title = (row.label || row.full_name || "").trim() || "—";
        const typeLabel = resolveCounterpartyTypeDisplay(row.counterparty_type);
        const cityLabel = (row.city_label || "").trim();
        const subtitle = [typeLabel, cityLabel].filter(Boolean).join(" • ");
        return (
          <button
            key={`${row.ref}:${row.counterparty_ref}:${title}`}
            type="button"
            data-nav-scope="waybill-recipient-counterparty"
            data-nav-index={index}
            className="flex min-h-10 w-full flex-col items-start justify-center gap-0.5 border-b px-3 py-1.5 text-left text-sm last:border-b-0"
            style={{
              borderColor: "var(--border)",
              backgroundColor: index === activeIndex ? "var(--surface-2)" : "var(--surface)",
            }}
            role="option"
            aria-selected={index === activeIndex}
            onMouseEnter={() => onActiveIndexChange(index)}
            onClick={() => onSelect(row)}
          >
            <span className="w-full truncate font-medium">{title}</span>
            {subtitle ? (
              <span className="w-full truncate text-[11px]" style={{ color: "var(--muted)" }}>
                {subtitle}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>,
    document.body,
  );
}

export function StreetDropdownPortal({
  dropdownRef,
  dropdownStyle,
  loading,
  rows,
  activeIndex,
  t,
  onActiveIndexChange,
  onSelect,
}: {
  dropdownRef: DropdownRef;
  dropdownStyle: DropdownStyle;
  loading: boolean;
  rows: BackofficeNovaPoshtaLookupStreet[];
  activeIndex: number;
  t: Translator;
  onActiveIndexChange: (index: number) => void;
  onSelect: (row: BackofficeNovaPoshtaLookupStreet) => void;
}) {
  if (!portalIsAvailable() || !dropdownStyle) {
    return null;
  }

  return createPortal(
    <div
      ref={dropdownRef}
      className="rounded-md border"
      style={{ ...dropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
      role="listbox"
      aria-label={t("orders.modals.waybill.fields.street")}
    >
      {loading ? (
        <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
      ) : rows.map((row, index) => (
        <button
          key={`${row.street_ref}:${row.label}`}
          type="button"
          data-nav-scope="waybill-street"
          data-nav-index={index}
          className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
          style={{
            borderColor: "var(--border)",
            backgroundColor: index === activeIndex ? "var(--surface-2)" : "var(--surface)",
          }}
          role="option"
          aria-selected={index === activeIndex}
          onMouseEnter={() => onActiveIndexChange(index)}
          onClick={() => onSelect(row)}
        >
          {row.label}
        </button>
      ))}
    </div>,
    document.body,
  );
}

export function WarehouseDropdownPortal({
  dropdownRef,
  dropdownStyle,
  loading,
  rows,
  activeIndex,
  t,
  onActiveIndexChange,
  onSelect,
}: {
  dropdownRef: DropdownRef;
  dropdownStyle: DropdownStyle;
  loading: boolean;
  rows: WaybillAddressSuggestion[];
  activeIndex: number;
  t: Translator;
  onActiveIndexChange: (index: number) => void;
  onSelect: (row: WaybillAddressSuggestion) => void;
}) {
  if (!portalIsAvailable() || !dropdownStyle) {
    return null;
  }

  return createPortal(
    <div
      ref={dropdownRef}
      className="rounded-md border"
      style={{ ...dropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
      role="listbox"
      aria-label={t("orders.modals.waybill.fields.warehouse")}
    >
      {loading ? (
        <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
      ) : rows.map((row, index) => (
        <button
          key={`${row.kind}:${row.ref}:${row.label}`}
          type="button"
          data-nav-scope="waybill-warehouse"
          data-nav-index={index}
          className="flex min-h-10 w-full flex-col items-start justify-center gap-0.5 border-b px-3 py-1.5 text-left text-sm last:border-b-0"
          style={{
            borderColor: "var(--border)",
            backgroundColor: index === activeIndex ? "var(--surface-2)" : "var(--surface)",
          }}
          role="option"
          aria-selected={index === activeIndex}
          onMouseEnter={() => onActiveIndexChange(index)}
          onClick={() => onSelect(row)}
        >
          <span className="w-full truncate font-medium">{row.label}</span>
          {row.subtitle ? (
            <span className="w-full truncate text-[11px]" style={{ color: "var(--muted)" }}>
              {row.subtitle}
            </span>
          ) : null}
        </button>
      ))}
    </div>,
    document.body,
  );
}

export function PackingsDropdownPortal({
  dropdownRef,
  dropdownStyle,
  loading,
  rows,
  selectedRefs,
  t,
  onToggle,
}: {
  dropdownRef: DropdownRef;
  dropdownStyle: DropdownStyle;
  loading: boolean;
  rows: BackofficeNovaPoshtaLookupPackaging[];
  selectedRefs: string[];
  t: Translator;
  onToggle: (row: BackofficeNovaPoshtaLookupPackaging) => void;
}) {
  if (!portalIsAvailable() || !dropdownStyle) {
    return null;
  }

  return createPortal(
    <div
      ref={dropdownRef}
      className="rounded-md border"
      style={{ ...dropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
      role="listbox"
      aria-label={t("orders.modals.waybill.fields.packRef")}
    >
      {loading ? (
        <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>
          {t("orders.modals.waybill.fields.packRefLoading")}
        </p>
      ) : rows.map((item) => {
        const isActive = selectedRefs.includes(item.ref);
        return (
          <button
            key={item.ref}
            type="button"
            className="flex min-h-10 w-full items-center border-b px-3 py-1.5 text-left text-sm last:border-b-0"
            style={{
              borderColor: "var(--border)",
              backgroundColor: isActive ? "var(--surface-2)" : "var(--surface)",
            }}
            role="option"
            aria-selected={isActive}
            onClick={() => onToggle(item)}
          >
            <span className="w-full truncate">{item.label || item.ref}</span>
          </button>
        );
      })}
    </div>,
    document.body,
  );
}
