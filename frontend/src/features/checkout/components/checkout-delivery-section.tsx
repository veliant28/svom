import Image from "next/image";
import { Store } from "lucide-react";
import type { Dispatch, RefObject, SetStateAction } from "react";

import type {
  CheckoutNovaPoshtaSettlement,
  CheckoutNovaPoshtaStreet,
  CheckoutNovaPoshtaWarehouse,
} from "@/features/checkout/api/lookup-nova-poshta";
import {
  CITY_LOOKUP_MIN_QUERY_LENGTH,
  STREET_LOOKUP_MIN_QUERY_LENGTH,
  formatWarehouseLookupDisplay,
  type CheckoutDeliveryOption,
} from "@/features/checkout/lib/checkout-page.helpers";

type Translator = (key: string, values?: Record<string, string | number>) => string;
type LookupRootRef = RefObject<HTMLLabelElement | null>;

export function CheckoutDeliverySection({
  deliveryOption,
  npDestinationLine1,
  npDestinationLine2,
  cityLookupRootRef,
  warehouseLookupRootRef,
  streetLookupRootRef,
  cityQuery,
  cityOptions,
  cityLoading,
  activeCityIndex,
  selectedCity,
  warehouseQuery,
  warehouseOptions,
  warehouseLoading,
  activeWarehouseIndex,
  streetQuery,
  streetOptions,
  streetLoading,
  activeStreetIndex,
  house,
  apartment,
  npLocale,
  t,
  setDeliveryOption,
  setCityQuery,
  setCityOptions,
  setActiveCityIndex,
  setSelectedCity,
  setWarehouseQuery,
  setWarehouseOptions,
  setActiveWarehouseIndex,
  setSelectedWarehouse,
  setStreetQuery,
  setStreetOptions,
  setActiveStreetIndex,
  setSelectedStreet,
  setHouse,
  setApartment,
  onCitySelect,
  onWarehouseSelect,
  onStreetSelect,
}: {
  deliveryOption: CheckoutDeliveryOption;
  npDestinationLine1: string;
  npDestinationLine2: string;
  cityLookupRootRef: LookupRootRef;
  warehouseLookupRootRef: LookupRootRef;
  streetLookupRootRef: LookupRootRef;
  cityQuery: string;
  cityOptions: CheckoutNovaPoshtaSettlement[];
  cityLoading: boolean;
  activeCityIndex: number;
  selectedCity: CheckoutNovaPoshtaSettlement | null;
  warehouseQuery: string;
  warehouseOptions: CheckoutNovaPoshtaWarehouse[];
  warehouseLoading: boolean;
  activeWarehouseIndex: number;
  streetQuery: string;
  streetOptions: CheckoutNovaPoshtaStreet[];
  streetLoading: boolean;
  activeStreetIndex: number;
  house: string;
  apartment: string;
  npLocale: string;
  t: Translator;
  setDeliveryOption: Dispatch<SetStateAction<CheckoutDeliveryOption>>;
  setCityQuery: Dispatch<SetStateAction<string>>;
  setCityOptions: Dispatch<SetStateAction<CheckoutNovaPoshtaSettlement[]>>;
  setActiveCityIndex: Dispatch<SetStateAction<number>>;
  setSelectedCity: Dispatch<SetStateAction<CheckoutNovaPoshtaSettlement | null>>;
  setWarehouseQuery: Dispatch<SetStateAction<string>>;
  setWarehouseOptions: Dispatch<SetStateAction<CheckoutNovaPoshtaWarehouse[]>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
  setSelectedWarehouse: Dispatch<SetStateAction<CheckoutNovaPoshtaWarehouse | null>>;
  setStreetQuery: Dispatch<SetStateAction<string>>;
  setStreetOptions: Dispatch<SetStateAction<CheckoutNovaPoshtaStreet[]>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  setSelectedStreet: Dispatch<SetStateAction<CheckoutNovaPoshtaStreet | null>>;
  setHouse: Dispatch<SetStateAction<string>>;
  setApartment: Dispatch<SetStateAction<string>>;
  onCitySelect: (item: CheckoutNovaPoshtaSettlement) => void;
  onWarehouseSelect: (item: CheckoutNovaPoshtaWarehouse) => void;
  onStreetSelect: (item: CheckoutNovaPoshtaStreet) => void;
}) {
  return (
    <>
      <h2 className="mt-5 text-lg font-semibold">{t("sections.delivery")}</h2>
      <div className="mt-3 grid gap-3">
        <div className="grid gap-2 sm:grid-cols-3">
          <button
            type="button"
            className="inline-flex h-[3.75rem] items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold"
            style={{
              borderColor: deliveryOption === "pickup" ? "var(--accent)" : "var(--border)",
              backgroundColor: deliveryOption === "pickup" ? "color-mix(in srgb, var(--accent) 12%, var(--surface))" : "var(--surface)",
            }}
            onClick={() => setDeliveryOption("pickup")}
          >
            <Store size={30} className="shrink-0" />
            <span className="leading-tight">{t("deliveryOptions.pickup")}</span>
          </button>
          <button
            type="button"
            className="inline-flex h-[3.75rem] items-center justify-between gap-2 rounded-md border px-3 text-sm font-semibold"
            style={{
              borderColor: deliveryOption === "nova_poshta_warehouse" ? "var(--accent)" : "var(--border)",
              backgroundColor: deliveryOption === "nova_poshta_warehouse" ? "color-mix(in srgb, var(--accent) 12%, var(--surface))" : "var(--surface)",
            }}
            onClick={() => setDeliveryOption("nova_poshta_warehouse")}
          >
            <span className="inline-flex min-w-0 items-center gap-2 leading-none">
              <Image src="/icons/nova-poshta.svg" alt="" width={30} height={30} className="h-[30px] w-[30px] shrink-0" aria-hidden />
              <span className="whitespace-nowrap">{t("delivery.novaPoshta")}</span>
            </span>
            <span className="shrink-0 text-right leading-[1.05]">
              <span className="block">{npDestinationLine1}</span>
              {npDestinationLine2 ? <span className="block">{npDestinationLine2}</span> : null}
            </span>
          </button>
          <button
            type="button"
            className="inline-flex h-[3.75rem] items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold"
            style={{
              borderColor: deliveryOption === "nova_poshta_courier" ? "var(--accent)" : "var(--border)",
              backgroundColor: deliveryOption === "nova_poshta_courier" ? "color-mix(in srgb, var(--accent) 12%, var(--surface))" : "var(--surface)",
            }}
            onClick={() => setDeliveryOption("nova_poshta_courier")}
          >
            <Image src="/icons/nova-poshta.svg" alt="" width={30} height={30} className="h-[30px] w-[30px] shrink-0" aria-hidden />
            <span className="leading-tight">{t("deliveryOptions.novaPoshtaCourier")}</span>
          </button>
        </div>

        {deliveryOption !== "pickup" ? (
          <label ref={cityLookupRootRef} className="relative flex flex-col gap-1 text-xs">
            {t("fields.npCity")}
            <input
              value={cityQuery}
              onChange={(event) => {
                const nextValue = event.target.value;
                setCityQuery(nextValue);
                setSelectedCity(null);
                setActiveCityIndex(-1);
                setCityOptions([]);
                setSelectedWarehouse(null);
                setWarehouseQuery("");
                setWarehouseOptions([]);
                setActiveWarehouseIndex(-1);
                setSelectedStreet(null);
                setStreetQuery("");
                setStreetOptions([]);
                setActiveStreetIndex(-1);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setCityOptions([]);
                  setActiveCityIndex(-1);
                  return;
                }
                if (!cityOptions.length) {
                  return;
                }
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveCityIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, cityOptions.length - 1)));
                  return;
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveCityIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                  return;
                }
                if (event.key === "Enter") {
                  event.preventDefault();
                  const resolvedIndex = activeCityIndex >= 0 ? activeCityIndex : 0;
                  const selected = cityOptions[resolvedIndex];
                  if (selected) {
                    onCitySelect(selected);
                  }
                }
              }}
              placeholder={t("placeholders.npCity")}
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
            {(cityLoading || cityOptions.length > 0) && cityQuery.trim().length >= CITY_LOOKUP_MIN_QUERY_LENGTH ? (
              <div className="absolute left-0 right-0 top-[3.5rem] z-20 max-h-56 overflow-auto rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                {cityLoading ? (
                  <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                    {t("lookup.loading")}
                  </div>
                ) : cityOptions.length ? (
                  cityOptions.map((item, index) => {
                    const meta = [item.main_description, item.area, item.region]
                      .map((value) => String(value || "").trim())
                      .filter(Boolean)
                      .join(" • ");
                    return (
                      <button
                        key={item.ref}
                        type="button"
                        data-nav-scope="checkout-city"
                        data-nav-index={index}
                        className="flex min-h-10 w-full flex-col items-start justify-center gap-0.5 border-b px-3 py-1.5 text-left text-xs last:border-b-0"
                        style={{
                          borderColor: "var(--border)",
                          backgroundColor: index === activeCityIndex ? "var(--surface-2)" : "var(--surface)",
                        }}
                        onMouseEnter={() => setActiveCityIndex(index)}
                        onClick={() => onCitySelect(item)}
                      >
                        <span className="w-full truncate font-medium">{item.label}</span>
                        {meta ? (
                          <span className="w-full truncate text-[11px]" style={{ color: "var(--muted)" }}>
                            {meta}
                          </span>
                        ) : null}
                      </button>
                    );
                  })
                ) : (
                  <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                    {t("lookup.noResults")}
                  </div>
                )}
              </div>
            ) : null}
          </label>
        ) : null}

        {deliveryOption === "nova_poshta_warehouse" ? (
          <label ref={warehouseLookupRootRef} className="relative flex flex-col gap-1 text-xs">
            {t("fields.npDestination")}
            <input
              value={warehouseQuery}
              disabled={!selectedCity}
              onChange={(event) => {
                setWarehouseQuery(event.target.value);
                setSelectedWarehouse(null);
                setWarehouseOptions([]);
                setActiveWarehouseIndex(-1);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setWarehouseOptions([]);
                  setActiveWarehouseIndex(-1);
                  return;
                }
                if (!warehouseOptions.length) {
                  return;
                }
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveWarehouseIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, warehouseOptions.length - 1)));
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
                  const selected = warehouseOptions[resolvedIndex];
                  if (selected) {
                    onWarehouseSelect(selected);
                  }
                }
              }}
              placeholder={t("placeholders.npDestination")}
              className="h-10 rounded-md border px-3 disabled:opacity-60"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
            {(warehouseLoading || warehouseOptions.length > 0) && selectedCity ? (
              <div className="absolute left-0 right-0 top-[3.5rem] z-20 max-h-56 overflow-auto rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                {warehouseLoading ? (
                  <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                    {t("lookup.loading")}
                  </div>
                ) : warehouseOptions.length ? (
                  warehouseOptions.map((item, index) => {
                    const display = formatWarehouseLookupDisplay(item, npLocale);
                    return (
                      <button
                        key={item.ref}
                        type="button"
                        data-nav-scope="checkout-warehouse"
                        data-nav-index={index}
                        className="flex min-h-10 w-full flex-col items-start justify-center gap-0.5 border-b px-3 py-1.5 text-left text-xs last:border-b-0"
                        style={{
                          borderColor: "var(--border)",
                          backgroundColor: index === activeWarehouseIndex ? "var(--surface-2)" : "var(--surface)",
                        }}
                        onMouseEnter={() => setActiveWarehouseIndex(index)}
                        onClick={() => onWarehouseSelect(item)}
                      >
                        <span className="w-full truncate font-medium">{display.label}</span>
                        {display.subtitle ? (
                          <span className="w-full truncate text-[11px]" style={{ color: "var(--muted)" }}>
                            {display.subtitle}
                          </span>
                        ) : null}
                      </button>
                    );
                  })
                ) : (
                  <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                    {t("lookup.noResults")}
                  </div>
                )}
              </div>
            ) : null}
          </label>
        ) : null}

        {deliveryOption === "nova_poshta_courier" ? (
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,0.45fr)_minmax(0,0.6fr)]">
            <label ref={streetLookupRootRef} className="relative flex flex-col gap-1 text-xs">
              {t("fields.npStreet")}
              <input
                value={streetQuery}
                disabled={!selectedCity}
                onChange={(event) => {
                  setStreetQuery(event.target.value);
                  setSelectedStreet(null);
                  setStreetOptions([]);
                  setActiveStreetIndex(-1);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setStreetOptions([]);
                    setActiveStreetIndex(-1);
                    return;
                  }
                  if (!streetOptions.length) {
                    return;
                  }
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    setActiveStreetIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, streetOptions.length - 1)));
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
                    const selected = streetOptions[resolvedIndex];
                    if (selected) {
                      onStreetSelect(selected);
                    }
                  }
                }}
                placeholder={t("placeholders.npStreet")}
                className="h-10 rounded-md border px-3 disabled:opacity-60"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
              {(streetLoading || streetOptions.length > 0) && streetQuery.trim().length >= STREET_LOOKUP_MIN_QUERY_LENGTH && selectedCity ? (
                <div className="absolute left-0 right-0 top-[3.5rem] z-20 max-h-56 overflow-auto rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  {streetLoading ? (
                    <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                      {t("lookup.loading")}
                    </div>
                  ) : streetOptions.length ? (
                    streetOptions.map((item, index) => (
                      <button
                        key={item.street_ref}
                        type="button"
                        data-nav-scope="checkout-street"
                        data-nav-index={index}
                        className="flex h-10 w-full items-center border-b px-3 text-left text-xs last:border-b-0"
                        style={{
                          borderColor: "var(--border)",
                          backgroundColor: index === activeStreetIndex ? "var(--surface-2)" : "var(--surface)",
                        }}
                        onMouseEnter={() => setActiveStreetIndex(index)}
                        onClick={() => onStreetSelect(item)}
                      >
                        {item.label}
                      </button>
                    ))
                  ) : (
                    <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                      {t("lookup.noResults")}
                    </div>
                  )}
                </div>
              ) : null}
            </label>

            <label className="flex flex-col gap-1 text-xs">
              {t("fields.npHouse")}
              <input
                value={house}
                onChange={(event) => setHouse(event.target.value)}
                placeholder={t("placeholders.npHouse")}
                required={deliveryOption === "nova_poshta_courier"}
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
            </label>

            <label className="flex flex-col gap-1 text-xs">
              {t("fields.npApartment")}
              <input
                value={apartment}
                onChange={(event) => setApartment(event.target.value)}
                placeholder={t("placeholders.npApartment")}
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
            </label>
          </div>
        ) : null}
      </div>
    </>
  );
}
