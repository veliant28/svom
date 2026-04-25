import { useEffect, type Dispatch, type RefObject, type SetStateAction } from "react";

import type { WaybillAddressSuggestion } from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
} from "@/features/backoffice/types/nova-poshta.types";

type ElementRef<T extends HTMLElement> = RefObject<T | null>;

export function useOrderWaybillOutsideClick({
  isOpen,
  senderMenuRef,
  seatMenuRef,
  recipientCounterpartyLookupRootRef,
  recipientCounterpartyDropdownRef,
  cityLookupRootRef,
  cityDropdownRef,
  streetLookupRootRef,
  streetDropdownRef,
  warehouseLookupRootRef,
  warehouseDropdownRef,
  packingsLookupRootRef,
  packingsDropdownRef,
  setSenderMenuOpen,
  setSeatMenuOpen,
  setRecipientCounterparties,
  setActiveRecipientCounterpartyIndex,
  setSettlements,
  setActiveSettlementIndex,
  setStreets,
  setActiveStreetIndex,
  setWarehouses,
  setActiveWarehouseIndex,
  setPackingsDropdownOpen,
}: {
  isOpen: boolean;
  senderMenuRef: ElementRef<HTMLDivElement>;
  seatMenuRef: ElementRef<HTMLDivElement>;
  recipientCounterpartyLookupRootRef: ElementRef<HTMLLabelElement>;
  recipientCounterpartyDropdownRef: ElementRef<HTMLDivElement>;
  cityLookupRootRef: ElementRef<HTMLLabelElement>;
  cityDropdownRef: ElementRef<HTMLDivElement>;
  streetLookupRootRef: ElementRef<HTMLLabelElement>;
  streetDropdownRef: ElementRef<HTMLDivElement>;
  warehouseLookupRootRef: ElementRef<HTMLLabelElement>;
  warehouseDropdownRef: ElementRef<HTMLDivElement>;
  packingsLookupRootRef: ElementRef<HTMLLabelElement>;
  packingsDropdownRef: ElementRef<HTMLDivElement>;
  setSenderMenuOpen: Dispatch<SetStateAction<boolean>>;
  setSeatMenuOpen: Dispatch<SetStateAction<boolean>>;
  setRecipientCounterparties: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupCounterparty[]>>;
  setActiveRecipientCounterpartyIndex: Dispatch<SetStateAction<number>>;
  setSettlements: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setActiveSettlementIndex: Dispatch<SetStateAction<number>>;
  setStreets: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupStreet[]>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  setWarehouses: Dispatch<SetStateAction<WaybillAddressSuggestion[]>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
  setPackingsDropdownOpen: Dispatch<SetStateAction<boolean>>;
}) {
  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleOutsideClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (senderMenuRef.current && !senderMenuRef.current.contains(target)) {
        setSenderMenuOpen(false);
      }
      if (seatMenuRef.current && !seatMenuRef.current.contains(target)) {
        setSeatMenuOpen(false);
      }
      const recipientCounterpartyInside = Boolean(
        recipientCounterpartyLookupRootRef.current?.contains(target)
        || recipientCounterpartyDropdownRef.current?.contains(target),
      );
      if (!recipientCounterpartyInside) {
        setRecipientCounterparties([]);
        setActiveRecipientCounterpartyIndex(-1);
      }
      const cityInside = Boolean(cityLookupRootRef.current?.contains(target) || cityDropdownRef.current?.contains(target));
      if (!cityInside) {
        setSettlements([]);
        setActiveSettlementIndex(-1);
      }
      const streetInside = Boolean(streetLookupRootRef.current?.contains(target) || streetDropdownRef.current?.contains(target));
      if (!streetInside) {
        setStreets([]);
        setActiveStreetIndex(-1);
      }
      const warehouseInside = Boolean(warehouseLookupRootRef.current?.contains(target) || warehouseDropdownRef.current?.contains(target));
      if (!warehouseInside) {
        setWarehouses([]);
        setActiveWarehouseIndex(-1);
      }
      const packingsInside = Boolean(packingsLookupRootRef.current?.contains(target) || packingsDropdownRef.current?.contains(target));
      if (!packingsInside) {
        setPackingsDropdownOpen(false);
      }
    };

    window.addEventListener("mousedown", handleOutsideClick);
    return () => {
      window.removeEventListener("mousedown", handleOutsideClick);
    };
  }, [
    cityDropdownRef,
    cityLookupRootRef,
    isOpen,
    packingsDropdownRef,
    packingsLookupRootRef,
    recipientCounterpartyDropdownRef,
    recipientCounterpartyLookupRootRef,
    seatMenuRef,
    senderMenuRef,
    setActiveRecipientCounterpartyIndex,
    setActiveSettlementIndex,
    setActiveStreetIndex,
    setActiveWarehouseIndex,
    setPackingsDropdownOpen,
    setRecipientCounterparties,
    setSeatMenuOpen,
    setSenderMenuOpen,
    setSettlements,
    setStreets,
    setWarehouses,
    streetDropdownRef,
    streetLookupRootRef,
    warehouseDropdownRef,
    warehouseLookupRootRef,
  ]);
}
