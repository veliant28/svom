import { useEffect, type Dispatch, type MutableRefObject, type RefObject, type SetStateAction } from "react";

import {
  lookupBackofficeNovaPoshtaCounterparties,
  lookupBackofficeNovaPoshtaSettlements,
  lookupBackofficeNovaPoshtaStreets,
  lookupBackofficeNovaPoshtaWarehouses,
} from "@/features/backoffice/api/orders-api";
import { useOrderWaybillServiceEffects } from "@/features/backoffice/components/orders/use-order-waybill-service-effects";
import {
  LETTER_QUERY_WAREHOUSE_LIMIT,
  formatWarehouseLookupDisplay,
  formatWarehouseSelectedLabel,
  splitAddressInput,
  type WaybillAddressSuggestion,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import {
  isCounterpartyBusinessCodeQuery,
  isSenderRefLike,
  normalizeCounterpartyBusinessCode,
  normalizeCounterpartyType,
} from "@/features/backoffice/components/orders/order-waybill-party.helpers";
import type { WaybillFormPayload } from "@/features/backoffice/lib/orders/waybill-form";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupDeliveryDate,
  BackofficeNovaPoshtaLookupPackaging,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
  BackofficeNovaPoshtaLookupTimeInterval,
} from "@/features/backoffice/types/nova-poshta.types";

export function useOrderWaybillLookupEffects({
  isOpen,
  token,
  locale,
  payload,
  setPayload,
  isPackagingEnabled,
  packagingWidth,
  packagingLength,
  packagingHeight,
  recipientCounterpartyQuery,
  skipNextRecipientCounterpartyLookupRef,
  setRecipientCounterpartyLoading,
  setRecipientCounterparties,
  setActiveRecipientCounterpartyIndex,
  cityLookupInteracted,
  cityQuery,
  skipNextSettlementLookupRef,
  setSettlementLoading,
  setSettlements,
  setActiveSettlementIndex,
  warehouseQuery,
  selectedSettlementRef,
  skipNextWarehouseLookupRef,
  setWarehouseLoading,
  setWarehouses,
  setActiveWarehouseIndex,
  streetInputRef,
  streetQuery,
  skipNextStreetLookupRef,
  setStreetLoading,
  setStreets,
  setActiveStreetIndex,
  isPackagingMode,
  setPackings,
  setPackingsLoading,
  isAdditionalServicesMode,
  normalizedPreferredDeliveryDate,
  setDeliveryDateLookup,
  setDeliveryDateLookupLoading,
  setTimeIntervals,
  setTimeIntervalsLoading,
  timeIntervals,
  timeIntervalsLoading,
}: {
  isOpen: boolean;
  token: string | null;
  locale: string;
  payload: WaybillFormPayload;
  setPayload: Dispatch<SetStateAction<WaybillFormPayload>>;
  isPackagingEnabled: boolean;
  packagingWidth: string;
  packagingLength: string;
  packagingHeight: string;
  recipientCounterpartyQuery: string;
  skipNextRecipientCounterpartyLookupRef: MutableRefObject<boolean>;
  setRecipientCounterpartyLoading: Dispatch<SetStateAction<boolean>>;
  setRecipientCounterparties: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupCounterparty[]>>;
  setActiveRecipientCounterpartyIndex: Dispatch<SetStateAction<number>>;
  cityLookupInteracted: boolean;
  cityQuery: string;
  skipNextSettlementLookupRef: MutableRefObject<boolean>;
  setSettlementLoading: Dispatch<SetStateAction<boolean>>;
  setSettlements: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setActiveSettlementIndex: Dispatch<SetStateAction<number>>;
  warehouseQuery: string;
  selectedSettlementRef: string;
  skipNextWarehouseLookupRef: MutableRefObject<boolean>;
  setWarehouseLoading: Dispatch<SetStateAction<boolean>>;
  setWarehouses: Dispatch<SetStateAction<WaybillAddressSuggestion[]>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
  streetInputRef: RefObject<HTMLInputElement | null>;
  streetQuery: string;
  skipNextStreetLookupRef: MutableRefObject<boolean>;
  setStreetLoading: Dispatch<SetStateAction<boolean>>;
  setStreets: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupStreet[]>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  isPackagingMode: boolean;
  setPackings: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupPackaging[]>>;
  setPackingsLoading: Dispatch<SetStateAction<boolean>>;
  isAdditionalServicesMode: boolean;
  normalizedPreferredDeliveryDate: string;
  setDeliveryDateLookup: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupDeliveryDate | null>>;
  setDeliveryDateLookupLoading: Dispatch<SetStateAction<boolean>>;
  setTimeIntervals: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupTimeInterval[]>>;
  setTimeIntervalsLoading: Dispatch<SetStateAction<boolean>>;
  timeIntervals: BackofficeNovaPoshtaLookupTimeInterval[];
  timeIntervalsLoading: boolean;
}) {
  useOrderWaybillServiceEffects({
    isOpen,
    token,
    locale,
    payload,
    setPayload,
    isPackagingEnabled,
    packagingWidth,
    packagingLength,
    packagingHeight,
    isPackagingMode,
    setPackings,
    setPackingsLoading,
    isAdditionalServicesMode,
    normalizedPreferredDeliveryDate,
    setDeliveryDateLookup,
    setDeliveryDateLookupLoading,
    setTimeIntervals,
    setTimeIntervalsLoading,
    timeIntervals,
    timeIntervalsLoading,
  });

  useEffect(() => {
    if (!isOpen || !token || !payload.sender_profile_id) {
      setRecipientCounterpartyLoading(false);
      return;
    }
    if (skipNextRecipientCounterpartyLookupRef.current) {
      skipNextRecipientCounterpartyLookupRef.current = false;
      setRecipientCounterpartyLoading(false);
      return;
    }
    const query = recipientCounterpartyQuery.trim();
    if (!query || isSenderRefLike(query) || normalizeCounterpartyType(query) === "private_person") {
      setRecipientCounterparties([]);
      setActiveRecipientCounterpartyIndex(-1);
      setRecipientCounterpartyLoading(false);
      return;
    }
    if (!isCounterpartyBusinessCodeQuery(query)) {
      setRecipientCounterparties([]);
      setActiveRecipientCounterpartyIndex(-1);
      setRecipientCounterpartyLoading(false);
      return;
    }
    const normalizedBusinessCode = normalizeCounterpartyBusinessCode(query);

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setRecipientCounterpartyLoading(true);
      try {
        const response = await lookupBackofficeNovaPoshtaCounterparties(token, {
          sender_profile_id: payload.sender_profile_id,
          query: normalizedBusinessCode,
          counterparty_property: "Recipient",
          locale,
        });
        if (!cancelled) {
          setRecipientCounterparties(response.results);
          setActiveRecipientCounterpartyIndex(response.results.length > 0 ? 0 : -1);
        }
      } catch {
        if (!cancelled) {
          setRecipientCounterparties([]);
          setActiveRecipientCounterpartyIndex(-1);
        }
      } finally {
        if (!cancelled) {
          setRecipientCounterpartyLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    isOpen,
    locale,
    payload.sender_profile_id,
    recipientCounterpartyQuery,
    setActiveRecipientCounterpartyIndex,
    setRecipientCounterparties,
    setRecipientCounterpartyLoading,
    skipNextRecipientCounterpartyLookupRef,
    token,
  ]);

  useEffect(() => {
    if (!isOpen || !token || !payload.sender_profile_id) {
      setSettlementLoading(false);
      return;
    }
    if (!cityLookupInteracted) {
      setSettlements([]);
      setActiveSettlementIndex(-1);
      setSettlementLoading(false);
      return;
    }
    if (skipNextSettlementLookupRef.current) {
      skipNextSettlementLookupRef.current = false;
      setSettlementLoading(false);
      return;
    }
    if (cityQuery.trim().length < 2) {
      setSettlements([]);
      setActiveSettlementIndex(-1);
      setSettlementLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setSettlementLoading(true);
      try {
        const response = await lookupBackofficeNovaPoshtaSettlements(token, {
          sender_profile_id: payload.sender_profile_id,
          query: cityQuery,
          locale,
        });
        if (!cancelled) {
          setSettlements(response.results);
          setActiveSettlementIndex(response.results.length > 0 ? 0 : -1);
        }
      } catch {
        if (!cancelled) {
          setSettlements([]);
          setActiveSettlementIndex(-1);
        }
      } finally {
        if (!cancelled) {
          setSettlementLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    cityLookupInteracted,
    cityQuery,
    isOpen,
    locale,
    payload.sender_profile_id,
    setActiveSettlementIndex,
    setSettlementLoading,
    setSettlements,
    skipNextSettlementLookupRef,
    token,
  ]);

  useEffect(() => {
    if (!isOpen || !token || !payload.sender_profile_id || !payload.recipient_city_ref) {
      setWarehouseLoading(false);
      return;
    }
    if (skipNextWarehouseLookupRef.current) {
      skipNextWarehouseLookupRef.current = false;
      setWarehouseLoading(false);
      return;
    }
    const { base: warehouseLookupQuery } = splitAddressInput(warehouseQuery);
    const hasCommaInAddressInput = warehouseQuery.includes(",");
    if (hasCommaInAddressInput) {
      setWarehouses([]);
      setActiveWarehouseIndex(-1);
      setWarehouseLoading(false);
      return;
    }
    const isDigitsOnlyWarehouseQuery = /^\d+$/.test(warehouseLookupQuery);
    const warehouseMinQueryLength = isDigitsOnlyWarehouseQuery ? 1 : 2;
    if (warehouseLookupQuery.length < warehouseMinQueryLength) {
      setWarehouses([]);
      setActiveWarehouseIndex(-1);
      setWarehouseLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setWarehouseLoading(true);
      try {
        const hasLetters = /[A-Za-zА-Яа-яІіЇїЄєҐґ]/.test(warehouseLookupQuery);
        const [warehousesResponse, streetsResponse] = await Promise.all([
          lookupBackofficeNovaPoshtaWarehouses(token, {
            sender_profile_id: payload.sender_profile_id,
            city_ref: payload.recipient_city_ref,
            query: warehouseLookupQuery,
            locale: "uk",
          }),
          hasLetters && Boolean(selectedSettlementRef.trim())
            ? lookupBackofficeNovaPoshtaStreets(token, {
              sender_profile_id: payload.sender_profile_id,
              settlement_ref: selectedSettlementRef,
              query: warehouseLookupQuery,
              locale,
            })
            : Promise.resolve({ results: [] as BackofficeNovaPoshtaLookupStreet[] }),
        ]);
        if (!cancelled) {
          const warehouseRows: WaybillAddressSuggestion[] = warehousesResponse.results.map((item) => {
            const formatted = formatWarehouseLookupDisplay(item);
            return {
              kind: "warehouse",
              ref: item.ref,
              label: formatted.label,
              subtitle: formatted.subtitle,
              selectedLabel: formatWarehouseSelectedLabel(item),
            };
          });
          const streetRows: WaybillAddressSuggestion[] = streetsResponse.results.map((item) => ({
            kind: "street",
            ref: item.street_ref,
            label: item.label || item.street_name || item.street_ref,
            subtitle: "",
            settlementRef: item.settlement_ref,
          }));
          const limitedWarehouseRows = hasLetters
            ? warehouseRows.slice(0, LETTER_QUERY_WAREHOUSE_LIMIT)
            : warehouseRows;
          const merged = hasLetters ? [...streetRows, ...limitedWarehouseRows] : warehouseRows;
          setWarehouses(merged);
          setActiveWarehouseIndex(merged.length > 0 ? 0 : -1);
        }
      } catch {
        if (!cancelled) {
          setWarehouses([]);
          setActiveWarehouseIndex(-1);
        }
      } finally {
        if (!cancelled) {
          setWarehouseLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    isOpen,
    locale,
    payload.recipient_city_ref,
    payload.sender_profile_id,
    selectedSettlementRef,
    setActiveWarehouseIndex,
    setWarehouseLoading,
    setWarehouses,
    skipNextWarehouseLookupRef,
    token,
    warehouseQuery,
  ]);

  useEffect(() => {
    if (!streetInputRef.current || !isOpen || !token || payload.delivery_type !== "address" || !payload.sender_profile_id || !selectedSettlementRef) {
      setStreetLoading(false);
      return;
    }
    if (skipNextStreetLookupRef.current) {
      skipNextStreetLookupRef.current = false;
      setStreetLoading(false);
      return;
    }
    if (streetQuery.trim().length < 2) {
      setStreets([]);
      setActiveStreetIndex(-1);
      setStreetLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setStreetLoading(true);
      try {
        const response = await lookupBackofficeNovaPoshtaStreets(token, {
          sender_profile_id: payload.sender_profile_id,
          settlement_ref: selectedSettlementRef,
          query: streetQuery,
          locale,
        });
        if (!cancelled) {
          setStreets(response.results);
          setActiveStreetIndex(response.results.length > 0 ? 0 : -1);
        }
      } catch {
        if (!cancelled) {
          setStreets([]);
          setActiveStreetIndex(-1);
        }
      } finally {
        if (!cancelled) {
          setStreetLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    isOpen,
    locale,
    payload.delivery_type,
    payload.sender_profile_id,
    selectedSettlementRef,
    setActiveStreetIndex,
    setStreetLoading,
    setStreets,
    skipNextStreetLookupRef,
    streetInputRef,
    streetQuery,
    token,
  ]);

}
