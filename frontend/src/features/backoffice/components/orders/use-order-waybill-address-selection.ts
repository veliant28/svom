import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from "react";

import {
  parseHouseApartmentFromSuffix,
  splitAddressInput,
  type WaybillAddressSuggestion,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type { WaybillFormPayload } from "@/features/backoffice/lib/orders/waybill-form";
import type {
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
} from "@/features/backoffice/types/nova-poshta.types";

export function useOrderWaybillAddressSelection({
  warehouseQuery,
  selectedSettlementRef,
  skipNextSettlementLookupRef,
  skipNextStreetLookupRef,
  skipNextWarehouseLookupRef,
  setPayload,
  setCityLookupInteracted,
  setSelectedSettlementRef,
  setCityQuery,
  setSettlements,
  setActiveSettlementIndex,
  setStreetQuery,
  setStreets,
  setActiveStreetIndex,
  setWarehouseQuery,
  setWarehouses,
  setActiveWarehouseIndex,
}: {
  warehouseQuery: string;
  selectedSettlementRef: string;
  skipNextSettlementLookupRef: MutableRefObject<boolean>;
  skipNextStreetLookupRef: MutableRefObject<boolean>;
  skipNextWarehouseLookupRef: MutableRefObject<boolean>;
  setPayload: Dispatch<SetStateAction<WaybillFormPayload>>;
  setCityLookupInteracted: Dispatch<SetStateAction<boolean>>;
  setSelectedSettlementRef: Dispatch<SetStateAction<string>>;
  setCityQuery: Dispatch<SetStateAction<string>>;
  setSettlements: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setActiveSettlementIndex: Dispatch<SetStateAction<number>>;
  setStreetQuery: Dispatch<SetStateAction<string>>;
  setStreets: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupStreet[]>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  setWarehouseQuery: Dispatch<SetStateAction<string>>;
  setWarehouses: Dispatch<SetStateAction<WaybillAddressSuggestion[]>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
}) {
  const applySettlementSelection = useCallback((settlement: BackofficeNovaPoshtaLookupSettlement) => {
    setCityLookupInteracted(false);
    skipNextSettlementLookupRef.current = true;
    setSelectedSettlementRef(settlement.settlement_ref || settlement.ref || "");
    setCityQuery(settlement.label);
    setSettlements([]);
    setActiveSettlementIndex(-1);
    setStreetQuery("");
    setStreets([]);
    setActiveStreetIndex(-1);
    setWarehouseQuery("");
    setWarehouses([]);
    setActiveWarehouseIndex(-1);
    setPayload((prev) => ({
      ...prev,
      recipient_city_ref: settlement.delivery_city_ref || settlement.ref,
      recipient_city_label: settlement.label,
      recipient_address_ref: "",
      recipient_address_label: "",
      recipient_street_ref: "",
      recipient_street_label: "",
      recipient_house: "",
      recipient_apartment: "",
    }));
  }, [
    setActiveSettlementIndex,
    setActiveStreetIndex,
    setActiveWarehouseIndex,
    setCityLookupInteracted,
    setCityQuery,
    setPayload,
    setSelectedSettlementRef,
    setSettlements,
    setStreetQuery,
    setStreets,
    setWarehouseQuery,
    setWarehouses,
    skipNextSettlementLookupRef,
  ]);

  const applyStreetSelection = useCallback((street: BackofficeNovaPoshtaLookupStreet) => {
    skipNextStreetLookupRef.current = true;
    setStreetQuery(street.label);
    setStreets([]);
    setActiveStreetIndex(-1);
    setPayload((prev) => ({
      ...prev,
      recipient_street_ref: street.street_ref,
      recipient_street_label: street.label,
    }));
  }, [setActiveStreetIndex, setPayload, setStreetQuery, setStreets, skipNextStreetLookupRef]);

  const applyWarehouseSuggestionSelection = useCallback((item: WaybillAddressSuggestion) => {
    setWarehouses([]);
    setActiveWarehouseIndex(-1);
    if (item.kind === "street") {
      const { suffix } = splitAddressInput(warehouseQuery);
      const { house, apartment } = parseHouseApartmentFromSuffix(suffix);
      const nextQuery = suffix ? `${item.label}, ${suffix}` : item.label;
      skipNextStreetLookupRef.current = true;
      skipNextWarehouseLookupRef.current = true;
      setSelectedSettlementRef(item.settlementRef || selectedSettlementRef);
      setWarehouseQuery(nextQuery);
      setStreets([]);
      setActiveStreetIndex(-1);
      setPayload((prev) => ({
        ...prev,
        delivery_type: "address",
        recipient_address_ref: "",
        recipient_address_label: "",
        recipient_street_ref: item.ref,
        recipient_street_label: item.label,
        recipient_house: house,
        recipient_apartment: apartment,
      }));
      return;
    }
    skipNextWarehouseLookupRef.current = true;
    const selectedLabel = (item.selectedLabel || item.label || "").trim();
    setWarehouseQuery(selectedLabel);
    const normalizedSuggestionText = `${item.label} ${item.subtitle}`.toLowerCase();
    const isPostomatSuggestion =
      normalizedSuggestionText.includes("поштомат")
      || normalizedSuggestionText.includes("почтомат")
      || normalizedSuggestionText.includes("постомат")
      || normalizedSuggestionText.includes("postomat");
    setPayload((prev) => ({
      ...prev,
      delivery_type: isPostomatSuggestion ? "postomat" : "warehouse",
      recipient_address_ref: item.ref,
      recipient_address_label: selectedLabel,
      recipient_street_ref: "",
      recipient_street_label: "",
      recipient_house: "",
      recipient_apartment: "",
    }));
  }, [
    selectedSettlementRef,
    setActiveStreetIndex,
    setActiveWarehouseIndex,
    setPayload,
    setSelectedSettlementRef,
    setStreets,
    setWarehouseQuery,
    setWarehouses,
    skipNextStreetLookupRef,
    skipNextWarehouseLookupRef,
    warehouseQuery,
  ]);

  return {
    applySettlementSelection,
    applyStreetSelection,
    applyWarehouseSuggestionSelection,
  };
}
