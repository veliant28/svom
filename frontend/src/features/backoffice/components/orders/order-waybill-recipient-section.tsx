import type { Dispatch, MutableRefObject, RefObject, SetStateAction } from "react";

import {
  parseHouseApartmentFromSuffix,
  splitAddressInput,
  type Translator,
  type WaybillAddressSuggestion,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import {
  normalizeWaybillPhone,
  type WaybillFormPayload,
} from "@/features/backoffice/lib/orders/waybill-form";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
} from "@/features/backoffice/types/nova-poshta.types";

export function OrderWaybillRecipientSection({
  recipientCounterpartyLookupRootRef,
  recipientCounterpartyInputRef,
  cityLookupRootRef,
  cityInputRef,
  warehouseLookupRootRef,
  warehouseInputRef,
  skipNextRecipientCounterpartyLookupRef,
  payload,
  recipientCounterpartyQuery,
  recipientCounterpartyTypeLabel,
  recipientCounterpartyLoading,
  recipientIsPrivatePerson,
  privateCounterpartyLabel,
  recipientCounterparties,
  activeRecipientCounterpartyIndex,
  cityQuery,
  settlements,
  activeSettlementIndex,
  warehouseQuery,
  warehouses,
  activeWarehouseIndex,
  warehouseLoading,
  formDisabled,
  t,
  setPayload,
  setRecipientCounterpartyTypeLabel,
  setRecipientCounterpartyTypeRaw,
  setRecipientCounterpartyQuery,
  setRecipientCounterparties,
  setActiveRecipientCounterpartyIndex,
  setCityLookupInteracted,
  setSelectedSettlementRef,
  setCityQuery,
  setSettlements,
  setActiveSettlementIndex,
  setStreets,
  setActiveStreetIndex,
  setWarehouses,
  setActiveWarehouseIndex,
  setWarehouseQuery,
  applyRecipientCounterpartySelection,
  applySettlementSelection,
  applyWarehouseSuggestionSelection,
}: {
  recipientCounterpartyLookupRootRef: RefObject<HTMLLabelElement | null>;
  recipientCounterpartyInputRef: RefObject<HTMLInputElement | null>;
  cityLookupRootRef: RefObject<HTMLLabelElement | null>;
  cityInputRef: RefObject<HTMLInputElement | null>;
  warehouseLookupRootRef: RefObject<HTMLLabelElement | null>;
  warehouseInputRef: RefObject<HTMLInputElement | null>;
  skipNextRecipientCounterpartyLookupRef: MutableRefObject<boolean>;
  payload: WaybillFormPayload;
  recipientCounterpartyQuery: string;
  recipientCounterpartyTypeLabel: string;
  recipientCounterpartyLoading: boolean;
  recipientIsPrivatePerson: boolean;
  privateCounterpartyLabel: string;
  recipientCounterparties: BackofficeNovaPoshtaLookupCounterparty[];
  activeRecipientCounterpartyIndex: number;
  cityQuery: string;
  settlements: BackofficeNovaPoshtaLookupSettlement[];
  activeSettlementIndex: number;
  warehouseQuery: string;
  warehouses: WaybillAddressSuggestion[];
  activeWarehouseIndex: number;
  warehouseLoading: boolean;
  formDisabled: boolean;
  t: Translator;
  setPayload: Dispatch<SetStateAction<WaybillFormPayload>>;
  setRecipientCounterpartyTypeLabel: Dispatch<SetStateAction<string>>;
  setRecipientCounterpartyTypeRaw: Dispatch<SetStateAction<string>>;
  setRecipientCounterpartyQuery: Dispatch<SetStateAction<string>>;
  setRecipientCounterparties: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupCounterparty[]>>;
  setActiveRecipientCounterpartyIndex: Dispatch<SetStateAction<number>>;
  setCityLookupInteracted: Dispatch<SetStateAction<boolean>>;
  setSelectedSettlementRef: Dispatch<SetStateAction<string>>;
  setCityQuery: Dispatch<SetStateAction<string>>;
  setSettlements: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setActiveSettlementIndex: Dispatch<SetStateAction<number>>;
  setStreets: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupStreet[]>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  setWarehouses: Dispatch<SetStateAction<WaybillAddressSuggestion[]>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
  setWarehouseQuery: Dispatch<SetStateAction<string>>;
  applyRecipientCounterpartySelection: (counterparty: BackofficeNovaPoshtaLookupCounterparty) => void;
  applySettlementSelection: (settlement: BackofficeNovaPoshtaLookupSettlement) => void;
  applyWarehouseSuggestionSelection: (item: WaybillAddressSuggestion) => void;
}) {
  return (
    <section
      className="order-3 rounded-md border p-3 xl:h-[460px]"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <div className="flex min-h-8 items-center gap-2">
        <h3 className="text-sm font-semibold">{t("orders.modals.waybill.sectionRecipient")}</h3>
      </div>

      <div className="grid gap-1 pt-0.5">
        <label className="grid gap-1 text-xs">
          <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.recipientPhone")}</span>
          <input
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            value={payload.recipient_phone}
            disabled={formDisabled}
            onChange={(event) => setPayload((prev) => ({ ...prev, recipient_phone: normalizeWaybillPhone(event.target.value) }))}
          />
        </label>

        <label ref={recipientCounterpartyLookupRootRef} className="grid gap-1 text-xs">
          <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.counterparty")}</span>
          <input
            ref={recipientCounterpartyInputRef}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            value={recipientCounterpartyQuery}
            disabled={formDisabled}
            onChange={(event) => {
              const next = event.target.value;
              setRecipientCounterpartyTypeLabel("");
              setRecipientCounterpartyTypeRaw("");
              setRecipientCounterpartyQuery(next);
              setRecipientCounterparties([]);
              setActiveRecipientCounterpartyIndex(-1);
              setPayload((prev) => ({
                ...prev,
                recipient_counterparty_ref: "",
                recipient_contact_ref: "",
              }));
            }}
            onBlur={() => {
              if (recipientCounterpartyQuery.trim()) {
                return;
              }
              skipNextRecipientCounterpartyLookupRef.current = true;
              setRecipientCounterpartyTypeLabel(privateCounterpartyLabel);
              setRecipientCounterpartyTypeRaw("PrivatePerson");
              setRecipientCounterpartyQuery(privateCounterpartyLabel);
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setRecipientCounterparties([]);
                setActiveRecipientCounterpartyIndex(-1);
                return;
              }
              if (!recipientCounterparties.length) {
                return;
              }
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setActiveRecipientCounterpartyIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, recipientCounterparties.length - 1)));
                return;
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setActiveRecipientCounterpartyIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                return;
              }
              if (event.key === "Enter") {
                event.preventDefault();
                const resolvedIndex = activeRecipientCounterpartyIndex >= 0 ? activeRecipientCounterpartyIndex : 0;
                const selected = recipientCounterparties[resolvedIndex];
                if (selected) {
                  applyRecipientCounterpartySelection(selected);
                }
              }
            }}
            placeholder={t("orders.modals.waybill.fields.counterparty")}
          />
          {recipientCounterpartyTypeLabel && !recipientIsPrivatePerson ? (
            <span className="truncate text-[11px]" style={{ color: "var(--muted)" }}>
              {recipientCounterpartyTypeLabel}
            </span>
          ) : null}
          {recipientCounterpartyLoading || !recipientIsPrivatePerson ? (
            <p className="text-[11px]" style={{ color: "var(--muted)" }}>
              {recipientCounterpartyLoading
                ? t("orders.modals.waybill.fields.counterpartyLookupLoading")
                : t("orders.modals.waybill.fields.counterpartyBusinessCodeHint")}
            </p>
          ) : null}
        </label>

        <label className="grid gap-1 text-xs">
          <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.recipientName")}</span>
          <input
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            value={payload.recipient_name}
            disabled={formDisabled}
            onChange={(event) => setPayload((prev) => ({ ...prev, recipient_name: event.target.value }))}
          />
        </label>

        <label ref={cityLookupRootRef} className="relative grid gap-1 text-xs">
          <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.city")}</span>
          <input
            ref={cityInputRef}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            value={cityQuery}
            disabled={formDisabled}
            onChange={(event) => {
              const next = event.target.value;
              setCityLookupInteracted(true);
              setSelectedSettlementRef("");
              setCityQuery(next);
              setSettlements([]);
              setActiveSettlementIndex(-1);
              setStreets([]);
              setActiveStreetIndex(-1);
              setWarehouses([]);
              setActiveWarehouseIndex(-1);
              setPayload((prev) => ({
                ...prev,
                recipient_city_ref: "",
                recipient_city_label: next,
                recipient_address_ref: "",
                recipient_address_label: "",
                recipient_street_ref: "",
                recipient_street_label: "",
                recipient_house: "",
                recipient_apartment: "",
              }));
            }}
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
                if (!selected) {
                  return;
                }
                applySettlementSelection(selected);
              }
            }}
            placeholder={t("orders.modals.waybill.fields.cityPlaceholder")}
          />
          {null}
        </label>

        <label ref={warehouseLookupRootRef} className="relative grid gap-1 text-xs">
          <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.warehouse")}</span>
          <input
            ref={warehouseInputRef}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            value={warehouseQuery}
            disabled={formDisabled || !payload.recipient_city_ref}
            onChange={(event) => {
              const next = event.target.value;
              const { base, suffix } = splitAddressInput(next);
              const { house, apartment } = parseHouseApartmentFromSuffix(suffix);
              const normalizedBase = base.trim().toLowerCase();
              setWarehouseQuery(next);
              setWarehouses([]);
              setActiveWarehouseIndex(-1);
              setStreets([]);
              setActiveStreetIndex(-1);
              setPayload((prev) => {
                const selectedStreetLabel = (prev.recipient_street_label || "").trim().toLowerCase();
                const keepStreetRef = Boolean(prev.recipient_street_ref && selectedStreetLabel && normalizedBase === selectedStreetLabel);
                const hasLettersInBase = /[A-Za-zА-Яа-яІіЇїЄєҐґ]/.test(base);
                if (keepStreetRef || hasLettersInBase) {
                  return {
                    ...prev,
                    delivery_type: "address",
                    recipient_address_ref: "",
                    recipient_address_label: "",
                    recipient_street_ref: keepStreetRef ? prev.recipient_street_ref : "",
                    recipient_street_label: keepStreetRef ? prev.recipient_street_label : base,
                    recipient_house: house,
                    recipient_apartment: apartment,
                  };
                }
                return {
                  ...prev,
                  delivery_type: prev.delivery_type === "postomat" ? "postomat" : "warehouse",
                  recipient_address_ref: "",
                  recipient_address_label: next,
                  recipient_street_ref: "",
                  recipient_street_label: "",
                  recipient_house: "",
                  recipient_apartment: "",
                };
              });
            }}
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
                if (!selected) {
                  return;
                }
                applyWarehouseSuggestionSelection(selected);
              }
            }}
            placeholder="Отделение / почтомат / адрес"
          />
          {null}
          <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
            {!payload.recipient_city_ref
              ? "Сначала выберите город."
              : warehouseLoading
                ? "Ищем отделения/почтоматы..."
                : "Цифры: от 1 символа, текст: от 2 символов. Для адреса: улица, дом/кв."}
          </p>
        </label>
      </div>
    </section>
  );
}
