import { useEffect, useState, type RefObject } from "react";

import {
  computeFloatingDropdownStyle,
  scrollDropdownOptionIntoView,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";

type ElementRef<T extends HTMLElement> = RefObject<T | null>;

export function useOrderWaybillFloatingDropdowns({
  isOpen,
  contentScrollRef,
  recipientCounterpartyInputRef,
  cityInputRef,
  streetInputRef,
  warehouseInputRef,
  packingsInputRef,
  recipientCounterpartyDropdownRef,
  cityDropdownRef,
  streetDropdownRef,
  warehouseDropdownRef,
  recipientCounterpartyLoading,
  recipientCounterpartiesCount,
  activeRecipientCounterpartyIndex,
  cityLookupInteracted,
  settlementLoading,
  settlementsCount,
  activeSettlementIndex,
  streetLoading,
  streetsCount,
  activeStreetIndex,
  warehouseLoading,
  warehousesCount,
  activeWarehouseIndex,
  isPackagingMode,
  packingsDropdownOpen,
  packingsLoading,
  visiblePackingsCount,
}: {
  isOpen: boolean;
  contentScrollRef: ElementRef<HTMLDivElement>;
  recipientCounterpartyInputRef: ElementRef<HTMLInputElement>;
  cityInputRef: ElementRef<HTMLInputElement>;
  streetInputRef: ElementRef<HTMLInputElement>;
  warehouseInputRef: ElementRef<HTMLInputElement>;
  packingsInputRef: ElementRef<HTMLInputElement>;
  recipientCounterpartyDropdownRef: ElementRef<HTMLDivElement>;
  cityDropdownRef: ElementRef<HTMLDivElement>;
  streetDropdownRef: ElementRef<HTMLDivElement>;
  warehouseDropdownRef: ElementRef<HTMLDivElement>;
  recipientCounterpartyLoading: boolean;
  recipientCounterpartiesCount: number;
  activeRecipientCounterpartyIndex: number;
  cityLookupInteracted: boolean;
  settlementLoading: boolean;
  settlementsCount: number;
  activeSettlementIndex: number;
  streetLoading: boolean;
  streetsCount: number;
  activeStreetIndex: number;
  warehouseLoading: boolean;
  warehousesCount: number;
  activeWarehouseIndex: number;
  isPackagingMode: boolean;
  packingsDropdownOpen: boolean;
  packingsLoading: boolean;
  visiblePackingsCount: number;
}) {
  const [, setFloatingTick] = useState(0);

  const hasAnyFloatingDropdown = (
    recipientCounterpartiesCount > 0
    || settlementsCount > 0
    || streetsCount > 0
    || warehousesCount > 0
    || (isPackagingMode && (packingsLoading || visiblePackingsCount > 0))
  );

  useEffect(() => {
    if (!isOpen || !hasAnyFloatingDropdown) {
      return;
    }
    const refresh = () => setFloatingTick((prev) => prev + 1);
    refresh();
    const contentEl = contentScrollRef.current;
    window.addEventListener("resize", refresh);
    window.addEventListener("scroll", refresh, true);
    contentEl?.addEventListener("scroll", refresh, { passive: true });
    return () => {
      window.removeEventListener("resize", refresh);
      window.removeEventListener("scroll", refresh, true);
      contentEl?.removeEventListener("scroll", refresh);
    };
  }, [contentScrollRef, hasAnyFloatingDropdown, isOpen]);

  useEffect(() => {
    if (!recipientCounterpartiesCount || activeRecipientCounterpartyIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(recipientCounterpartyDropdownRef.current, "waybill-recipient-counterparty", activeRecipientCounterpartyIndex);
  }, [activeRecipientCounterpartyIndex, recipientCounterpartiesCount, recipientCounterpartyDropdownRef]);

  useEffect(() => {
    if (!settlementsCount || activeSettlementIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(cityDropdownRef.current, "waybill-city", activeSettlementIndex);
  }, [activeSettlementIndex, cityDropdownRef, settlementsCount]);

  useEffect(() => {
    if (!streetsCount || activeStreetIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(streetDropdownRef.current, "waybill-street", activeStreetIndex);
  }, [activeStreetIndex, streetDropdownRef, streetsCount]);

  useEffect(() => {
    if (!warehousesCount || activeWarehouseIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(warehouseDropdownRef.current, "waybill-warehouse", activeWarehouseIndex);
  }, [activeWarehouseIndex, warehouseDropdownRef, warehousesCount]);

  return {
    recipientCounterpartyDropdownStyle: (recipientCounterpartyLoading || recipientCounterpartiesCount > 0)
      ? computeFloatingDropdownStyle(recipientCounterpartyInputRef.current)
      : null,
    cityDropdownStyle: cityLookupInteracted && (settlementLoading || settlementsCount > 0)
      ? computeFloatingDropdownStyle(cityInputRef.current)
      : null,
    streetDropdownStyle: (streetLoading || streetsCount > 0)
      ? computeFloatingDropdownStyle(streetInputRef.current)
      : null,
    warehouseDropdownStyle: (warehouseLoading || warehousesCount > 0)
      ? computeFloatingDropdownStyle(warehouseInputRef.current)
      : null,
    packingsDropdownStyle: (isPackagingMode && (packingsLoading || visiblePackingsCount > 0)) && packingsDropdownOpen
      ? computeFloatingDropdownStyle(packingsInputRef.current, { maxHeight: 420 })
      : null,
  };
}
