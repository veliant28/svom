import type { Dispatch, RefObject, SetStateAction } from "react";

import { formatWarehouseLookupDisplay } from "@/features/backoffice/components/orders/nova-poshta-senders.helpers";
import type {
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
  BackofficeNovaPoshtaLookupWarehouse,
} from "@/features/backoffice/types/nova-poshta.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;
type LookupRootRef = RefObject<HTMLDivElement | null>;

export function NovaPoshtaSendersLookupPanel({
  canLookup,
  lookupSettlementRef,
  lookupCityRef,
  settlementLookupRootRef,
  streetLookupRootRef,
  warehouseLookupRootRef,
  settlementQuery,
  streetQuery,
  warehouseQuery,
  settlements,
  streets,
  warehouses,
  settlementLoading,
  streetLoading,
  warehouseLoading,
  activeSettlementIndex,
  activeStreetIndex,
  activeWarehouseIndex,
  t,
  onSettlementQueryChange,
  onStreetQueryChange,
  onWarehouseQueryChange,
  setSettlements,
  setStreets,
  setWarehouses,
  setActiveSettlementIndex,
  setActiveStreetIndex,
  setActiveWarehouseIndex,
  onSettlementSelect,
  onStreetSelect,
  onWarehouseSelect,
}: {
  canLookup: boolean;
  lookupSettlementRef: string;
  lookupCityRef: string;
  settlementLookupRootRef: LookupRootRef;
  streetLookupRootRef: LookupRootRef;
  warehouseLookupRootRef: LookupRootRef;
  settlementQuery: string;
  streetQuery: string;
  warehouseQuery: string;
  settlements: BackofficeNovaPoshtaLookupSettlement[];
  streets: BackofficeNovaPoshtaLookupStreet[];
  warehouses: BackofficeNovaPoshtaLookupWarehouse[];
  settlementLoading: boolean;
  streetLoading: boolean;
  warehouseLoading: boolean;
  activeSettlementIndex: number;
  activeStreetIndex: number;
  activeWarehouseIndex: number;
  t: Translator;
  onSettlementQueryChange: (value: string) => void;
  onStreetQueryChange: (value: string) => void;
  onWarehouseQueryChange: (value: string) => void;
  setSettlements: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setStreets: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupStreet[]>>;
  setWarehouses: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupWarehouse[]>>;
  setActiveSettlementIndex: Dispatch<SetStateAction<number>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
  onSettlementSelect: (item: BackofficeNovaPoshtaLookupSettlement) => void;
  onStreetSelect: (item: BackofficeNovaPoshtaLookupStreet) => void;
  onWarehouseSelect: (item: BackofficeNovaPoshtaLookupWarehouse) => void;
}) {
  return (
    <aside className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="mb-3">
        <h3 className="text-sm font-semibold">{t("orders.modals.waybill.settings.lookup.title")}</h3>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
          {t("orders.modals.waybill.settings.lookup.subtitle")}
        </p>
      </div>

      <div className="mt-3 grid gap-3">
        <div className="rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <p className="mb-1 text-xs font-semibold">{t("orders.modals.waybill.settings.lookup.settlements")}</p>
          <div ref={settlementLookupRootRef} className="relative">
            <input
              className="h-9 w-full rounded-md border px-2 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              value={settlementQuery}
              onChange={(event) => onSettlementQueryChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setSettlements([]);
                  setActiveSettlementIndex(-1);
                  return;
                }
                if (!settlements.length) {
                  return;
                }
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveSettlementIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, settlements.length - 1)));
                  return;
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveSettlementIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                  return;
                }
                if (event.key === "Enter") {
                  event.preventDefault();
                  const resolvedIndex = activeSettlementIndex >= 0 ? activeSettlementIndex : 0;
                  const selected = settlements[resolvedIndex];
                  if (selected) {
                    onSettlementSelect(selected);
                  }
                }
              }}
              placeholder={t("orders.modals.waybill.settings.lookup.searchPlaceholder")}
            />
            {settlements.length ? (
              <div
                className="absolute left-0 right-0 top-10 z-20 max-h-44 overflow-auto rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                role="listbox"
                aria-label={t("orders.modals.waybill.settings.lookup.settlements")}
              >
                {settlements.map((row, index) => (
                  <button
                    key={row.ref}
                    type="button"
                    data-nav-scope="lookup-settlement"
                    data-nav-index={index}
                    className="flex h-9 w-full items-center border-b px-2 text-left text-xs last:border-b-0"
                    style={{
                      borderColor: "var(--border)",
                      backgroundColor: index === activeSettlementIndex ? "var(--surface-2)" : "var(--surface)",
                    }}
                    role="option"
                    aria-selected={index === activeSettlementIndex}
                    onMouseEnter={() => setActiveSettlementIndex(index)}
                    onClick={() => onSettlementSelect(row)}
                  >
                    <span className="truncate font-medium">{row.label}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
            {!canLookup
              ? "Выберите отправителя с токеном."
              : settlementLoading
                ? "Ищем города..."
                : "Введите минимум 2 символа."}
          </p>
        </div>

        <div className="rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <p className="mb-1 text-xs font-semibold">{t("orders.modals.waybill.settings.lookup.streets")}</p>
          <div ref={streetLookupRootRef} className="relative">
            <input
              className="h-9 w-full rounded-md border px-2 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              value={streetQuery}
              onChange={(event) => onStreetQueryChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setStreets([]);
                  setActiveStreetIndex(-1);
                  return;
                }
                if (!streets.length) {
                  return;
                }
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveStreetIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, streets.length - 1)));
                  return;
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveStreetIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                  return;
                }
                if (event.key === "Enter") {
                  event.preventDefault();
                  const resolvedIndex = activeStreetIndex >= 0 ? activeStreetIndex : 0;
                  const selected = streets[resolvedIndex];
                  if (selected) {
                    onStreetSelect(selected);
                  }
                }
              }}
              placeholder={t("orders.modals.waybill.settings.lookup.searchPlaceholder")}
            />
            {streets.length ? (
              <div
                className="absolute left-0 right-0 top-10 z-20 max-h-44 overflow-auto rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                role="listbox"
                aria-label={t("orders.modals.waybill.settings.lookup.streets")}
              >
                {streets.map((row, index) => (
                  <button
                    key={row.street_ref}
                    type="button"
                    data-nav-scope="lookup-street"
                    data-nav-index={index}
                    className="flex h-9 w-full items-center border-b px-2 text-left text-xs last:border-b-0"
                    style={{
                      borderColor: "var(--border)",
                      backgroundColor: index === activeStreetIndex ? "var(--surface-2)" : "var(--surface)",
                    }}
                    role="option"
                    aria-selected={index === activeStreetIndex}
                    onMouseEnter={() => setActiveStreetIndex(index)}
                    onClick={() => onStreetSelect(row)}
                  >
                    <span className="truncate font-medium">{row.label}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
            {!canLookup
              ? "Выберите отправителя с токеном."
              : !lookupSettlementRef
                ? "Сначала выберите город."
                : streetLoading
                  ? "Ищем улицы..."
                  : "Введите минимум 2 символа."}
          </p>
        </div>

        <div className="rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <p className="mb-1 text-xs font-semibold">{t("orders.modals.waybill.settings.lookup.warehouses")}</p>
          <div ref={warehouseLookupRootRef} className="relative">
            <input
              className="h-9 w-full rounded-md border px-2 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              value={warehouseQuery}
              onChange={(event) => onWarehouseQueryChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setWarehouses([]);
                  setActiveWarehouseIndex(-1);
                  return;
                }
                if (!warehouses.length) {
                  return;
                }
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveWarehouseIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, warehouses.length - 1)));
                  return;
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveWarehouseIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                  return;
                }
                if (event.key === "Enter") {
                  event.preventDefault();
                  const resolvedIndex = activeWarehouseIndex >= 0 ? activeWarehouseIndex : 0;
                  const selected = warehouses[resolvedIndex];
                  if (selected) {
                    onWarehouseSelect(selected);
                  }
                }
              }}
              placeholder={t("orders.modals.waybill.settings.lookup.searchPlaceholder")}
            />
            {warehouses.length ? (
              <div
                className="absolute left-0 right-0 top-10 z-20 max-h-44 overflow-auto rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                role="listbox"
                aria-label={t("orders.modals.waybill.settings.lookup.warehouses")}
              >
                {warehouses.map((row, index) => {
                  const formatted = formatWarehouseLookupDisplay(row);
                  return (
                    <button
                      key={row.ref}
                      type="button"
                      data-nav-scope="lookup-warehouse"
                      data-nav-index={index}
                      className="flex h-10 w-full items-center border-b px-2 text-left text-xs last:border-b-0"
                      style={{
                        borderColor: "var(--border)",
                        backgroundColor: index === activeWarehouseIndex ? "var(--surface-2)" : "var(--surface)",
                      }}
                      role="option"
                      aria-selected={index === activeWarehouseIndex}
                      onMouseEnter={() => setActiveWarehouseIndex(index)}
                      onClick={() => onWarehouseSelect(row)}
                    >
                      <span className="truncate font-medium">{formatted.label}</span>
                      {formatted.subtitle ? (
                        <span className="ml-2 shrink-0 text-[11px]" style={{ color: "var(--muted)" }}>
                          {formatted.subtitle}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>
          <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
            {!canLookup
              ? "Выберите отправителя с токеном."
              : !lookupCityRef
                ? "Сначала выберите город."
                : warehouseLoading
                  ? "Ищем отделения/почтоматы..."
                  : "Цифры: от 1 символа, текст: от 2 символов."}
          </p>
        </div>
      </div>
    </aside>
  );
}
