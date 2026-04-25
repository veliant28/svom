import { useEffect, type Dispatch, type MutableRefObject, type RefObject, type SetStateAction } from "react";

import { scrollDropdownOptionIntoView } from "@/features/backoffice/components/orders/nova-poshta-senders.helpers";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
  BackofficeNovaPoshtaLookupWarehouse,
} from "@/features/backoffice/types/nova-poshta.types";
import type { ModalAddressSuggestion } from "@/features/backoffice/components/orders/nova-poshta-senders.helpers";

type LookupRootRef = RefObject<HTMLDivElement | null>;

export function useNovaPoshtaSendersDropdownEffects({
  isEditorOpen,
  counterpartyQuery,
  modalCityQuery,
  modalAddressQuery,
  counterparties,
  modalCities,
  modalAddresses,
  settlements,
  streets,
  warehouses,
  activeCounterpartyIndex,
  activeModalCityIndex,
  activeModalAddressIndex,
  activeSettlementIndex,
  activeStreetIndex,
  activeWarehouseIndex,
  counterpartyLookupRootRef,
  modalCityLookupRootRef,
  modalAddressLookupRootRef,
  settlementLookupRootRef,
  streetLookupRootRef,
  warehouseLookupRootRef,
  skipNextCounterpartyLookupRef,
  skipNextModalCityLookupRef,
  skipNextModalAddressLookupRef,
  runCounterpartyLookup,
  runModalCityLookup,
  runModalAddressLookup,
  setCounterparties,
  setModalCities,
  setModalAddresses,
  setSettlements,
  setStreets,
  setWarehouses,
  setActiveCounterpartyIndex,
  setActiveModalCityIndex,
  setActiveModalAddressIndex,
  setActiveSettlementIndex,
  setActiveStreetIndex,
  setActiveWarehouseIndex,
}: {
  isEditorOpen: boolean;
  counterpartyQuery: string;
  modalCityQuery: string;
  modalAddressQuery: string;
  counterparties: BackofficeNovaPoshtaLookupCounterparty[];
  modalCities: BackofficeNovaPoshtaLookupSettlement[];
  modalAddresses: ModalAddressSuggestion[];
  settlements: BackofficeNovaPoshtaLookupSettlement[];
  streets: BackofficeNovaPoshtaLookupStreet[];
  warehouses: BackofficeNovaPoshtaLookupWarehouse[];
  activeCounterpartyIndex: number;
  activeModalCityIndex: number;
  activeModalAddressIndex: number;
  activeSettlementIndex: number;
  activeStreetIndex: number;
  activeWarehouseIndex: number;
  counterpartyLookupRootRef: LookupRootRef;
  modalCityLookupRootRef: LookupRootRef;
  modalAddressLookupRootRef: LookupRootRef;
  settlementLookupRootRef: LookupRootRef;
  streetLookupRootRef: LookupRootRef;
  warehouseLookupRootRef: LookupRootRef;
  skipNextCounterpartyLookupRef: MutableRefObject<boolean>;
  skipNextModalCityLookupRef: MutableRefObject<boolean>;
  skipNextModalAddressLookupRef: MutableRefObject<boolean>;
  runCounterpartyLookup: (query: string) => Promise<void>;
  runModalCityLookup: (query: string) => Promise<void>;
  runModalAddressLookup: (query: string) => Promise<void>;
  setCounterparties: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupCounterparty[]>>;
  setModalCities: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setModalAddresses: Dispatch<SetStateAction<ModalAddressSuggestion[]>>;
  setSettlements: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setStreets: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupStreet[]>>;
  setWarehouses: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupWarehouse[]>>;
  setActiveCounterpartyIndex: Dispatch<SetStateAction<number>>;
  setActiveModalCityIndex: Dispatch<SetStateAction<number>>;
  setActiveModalAddressIndex: Dispatch<SetStateAction<number>>;
  setActiveSettlementIndex: Dispatch<SetStateAction<number>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
}) {
  useEffect(() => {
    if (!isEditorOpen) {
      return;
    }
    if (skipNextCounterpartyLookupRef.current) {
      skipNextCounterpartyLookupRef.current = false;
      return;
    }
    const timerId = window.setTimeout(() => {
      void runCounterpartyLookup(counterpartyQuery);
    }, 280);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [counterpartyQuery, isEditorOpen, runCounterpartyLookup, skipNextCounterpartyLookupRef]);

  useEffect(() => {
    if (!isEditorOpen) {
      return;
    }
    if (skipNextModalCityLookupRef.current) {
      skipNextModalCityLookupRef.current = false;
      return;
    }
    const timerId = window.setTimeout(() => {
      void runModalCityLookup(modalCityQuery);
    }, 280);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [isEditorOpen, modalCityQuery, runModalCityLookup, skipNextModalCityLookupRef]);

  useEffect(() => {
    if (!isEditorOpen) {
      return;
    }
    if (skipNextModalAddressLookupRef.current) {
      skipNextModalAddressLookupRef.current = false;
      return;
    }
    const timerId = window.setTimeout(() => {
      void runModalAddressLookup(modalAddressQuery);
    }, 280);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [isEditorOpen, modalAddressQuery, runModalAddressLookup, skipNextModalAddressLookupRef]);

  useEffect(() => {
    if (!isEditorOpen || (!counterparties.length && !modalCities.length && !modalAddresses.length)) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!counterpartyLookupRootRef.current?.contains(target)) {
        setCounterparties([]);
        setActiveCounterpartyIndex(-1);
      }
      if (!modalCityLookupRootRef.current?.contains(target)) {
        setModalCities([]);
        setActiveModalCityIndex(-1);
      }
      if (!modalAddressLookupRootRef.current?.contains(target)) {
        setModalAddresses([]);
        setActiveModalAddressIndex(-1);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [
    counterparties.length,
    counterpartyLookupRootRef,
    isEditorOpen,
    modalAddressLookupRootRef,
    modalAddresses.length,
    modalCities.length,
    modalCityLookupRootRef,
    setActiveCounterpartyIndex,
    setActiveModalAddressIndex,
    setActiveModalCityIndex,
    setCounterparties,
    setModalAddresses,
    setModalCities,
  ]);

  useEffect(() => {
    if (!settlements.length && !streets.length && !warehouses.length) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!settlementLookupRootRef.current?.contains(target)) {
        setSettlements([]);
        setActiveSettlementIndex(-1);
      }
      if (!streetLookupRootRef.current?.contains(target)) {
        setStreets([]);
        setActiveStreetIndex(-1);
      }
      if (!warehouseLookupRootRef.current?.contains(target)) {
        setWarehouses([]);
        setActiveWarehouseIndex(-1);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [
    settlementLookupRootRef,
    settlements.length,
    setActiveSettlementIndex,
    setActiveStreetIndex,
    setActiveWarehouseIndex,
    setSettlements,
    setStreets,
    setWarehouses,
    streetLookupRootRef,
    streets.length,
    warehouseLookupRootRef,
    warehouses.length,
  ]);

  useEffect(() => {
    if (!counterparties.length || activeCounterpartyIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(counterpartyLookupRootRef.current, "counterparty", activeCounterpartyIndex);
  }, [activeCounterpartyIndex, counterparties.length, counterpartyLookupRootRef]);

  useEffect(() => {
    if (!modalCities.length || activeModalCityIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(modalCityLookupRootRef.current, "modal-city", activeModalCityIndex);
  }, [activeModalCityIndex, modalCities.length, modalCityLookupRootRef]);

  useEffect(() => {
    if (!modalAddresses.length || activeModalAddressIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(modalAddressLookupRootRef.current, "modal-address", activeModalAddressIndex);
  }, [activeModalAddressIndex, modalAddresses.length, modalAddressLookupRootRef]);

  useEffect(() => {
    if (!settlements.length || activeSettlementIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(settlementLookupRootRef.current, "lookup-settlement", activeSettlementIndex);
  }, [activeSettlementIndex, settlementLookupRootRef, settlements.length]);

  useEffect(() => {
    if (!streets.length || activeStreetIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(streetLookupRootRef.current, "lookup-street", activeStreetIndex);
  }, [activeStreetIndex, streetLookupRootRef, streets.length]);

  useEffect(() => {
    if (!warehouses.length || activeWarehouseIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(warehouseLookupRootRef.current, "lookup-warehouse", activeWarehouseIndex);
  }, [activeWarehouseIndex, warehouseLookupRootRef, warehouses.length]);
}
