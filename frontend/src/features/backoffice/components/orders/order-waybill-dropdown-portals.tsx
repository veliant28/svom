import type { CSSProperties, RefObject } from "react";

import {
  CityDropdownPortal,
  PackingsDropdownPortal,
  RecipientCounterpartyDropdownPortal,
  StreetDropdownPortal,
  WarehouseDropdownPortal,
} from "@/features/backoffice/components/orders/order-waybill-modal-dropdowns";
import type {
  Translator,
  WaybillAddressSuggestion,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupPackaging,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
} from "@/features/backoffice/types/nova-poshta.types";

type DropdownStyle = CSSProperties | null;
type DropdownRef = RefObject<HTMLDivElement | null>;

export function OrderWaybillDropdownPortals({
  cityDropdownRef,
  cityDropdownStyle,
  settlementLoading,
  settlements,
  activeSettlementIndex,
  recipientCounterpartyDropdownRef,
  recipientCounterpartyDropdownStyle,
  recipientCounterpartyLoading,
  recipientCounterparties,
  activeRecipientCounterpartyIndex,
  streetDropdownRef,
  streetDropdownStyle,
  streetLoading,
  streets,
  activeStreetIndex,
  warehouseDropdownRef,
  warehouseDropdownStyle,
  warehouseLoading,
  warehouses,
  activeWarehouseIndex,
  packingsDropdownRef,
  packingsDropdownStyle,
  packingsLoading,
  visiblePackings,
  selectedPackRefs,
  t,
  setActiveSettlementIndex,
  applySettlementSelection,
  setActiveRecipientCounterpartyIndex,
  applyRecipientCounterpartySelection,
  setActiveStreetIndex,
  applyStreetSelection,
  setActiveWarehouseIndex,
  applyWarehouseSuggestionSelection,
  togglePackagingSelection,
}: {
  cityDropdownRef: DropdownRef;
  cityDropdownStyle: DropdownStyle;
  settlementLoading: boolean;
  settlements: BackofficeNovaPoshtaLookupSettlement[];
  activeSettlementIndex: number;
  recipientCounterpartyDropdownRef: DropdownRef;
  recipientCounterpartyDropdownStyle: DropdownStyle;
  recipientCounterpartyLoading: boolean;
  recipientCounterparties: BackofficeNovaPoshtaLookupCounterparty[];
  activeRecipientCounterpartyIndex: number;
  streetDropdownRef: DropdownRef;
  streetDropdownStyle: DropdownStyle;
  streetLoading: boolean;
  streets: BackofficeNovaPoshtaLookupStreet[];
  activeStreetIndex: number;
  warehouseDropdownRef: DropdownRef;
  warehouseDropdownStyle: DropdownStyle;
  warehouseLoading: boolean;
  warehouses: WaybillAddressSuggestion[];
  activeWarehouseIndex: number;
  packingsDropdownRef: DropdownRef;
  packingsDropdownStyle: DropdownStyle;
  packingsLoading: boolean;
  visiblePackings: BackofficeNovaPoshtaLookupPackaging[];
  selectedPackRefs: string[];
  t: Translator;
  setActiveSettlementIndex: (index: number) => void;
  applySettlementSelection: (row: BackofficeNovaPoshtaLookupSettlement) => void;
  setActiveRecipientCounterpartyIndex: (index: number) => void;
  applyRecipientCounterpartySelection: (row: BackofficeNovaPoshtaLookupCounterparty) => void;
  setActiveStreetIndex: (index: number) => void;
  applyStreetSelection: (row: BackofficeNovaPoshtaLookupStreet) => void;
  setActiveWarehouseIndex: (index: number) => void;
  applyWarehouseSuggestionSelection: (row: WaybillAddressSuggestion) => void;
  togglePackagingSelection: (row: BackofficeNovaPoshtaLookupPackaging) => void;
}) {
  return (
    <>
      <CityDropdownPortal
        dropdownRef={cityDropdownRef}
        dropdownStyle={cityDropdownStyle}
        loading={settlementLoading}
        rows={settlements}
        activeIndex={activeSettlementIndex}
        t={t}
        onActiveIndexChange={setActiveSettlementIndex}
        onSelect={applySettlementSelection}
      />
      <RecipientCounterpartyDropdownPortal
        dropdownRef={recipientCounterpartyDropdownRef}
        dropdownStyle={recipientCounterpartyDropdownStyle}
        loading={recipientCounterpartyLoading}
        rows={recipientCounterparties}
        activeIndex={activeRecipientCounterpartyIndex}
        t={t}
        onActiveIndexChange={setActiveRecipientCounterpartyIndex}
        onSelect={applyRecipientCounterpartySelection}
      />
      <StreetDropdownPortal
        dropdownRef={streetDropdownRef}
        dropdownStyle={streetDropdownStyle}
        loading={streetLoading}
        rows={streets}
        activeIndex={activeStreetIndex}
        t={t}
        onActiveIndexChange={setActiveStreetIndex}
        onSelect={applyStreetSelection}
      />
      <WarehouseDropdownPortal
        dropdownRef={warehouseDropdownRef}
        dropdownStyle={warehouseDropdownStyle}
        loading={warehouseLoading}
        rows={warehouses}
        activeIndex={activeWarehouseIndex}
        t={t}
        onActiveIndexChange={setActiveWarehouseIndex}
        onSelect={applyWarehouseSuggestionSelection}
      />
      <PackingsDropdownPortal
        dropdownRef={packingsDropdownRef}
        dropdownStyle={packingsDropdownStyle}
        loading={packingsLoading}
        rows={visiblePackings}
        selectedRefs={selectedPackRefs}
        t={t}
        onToggle={togglePackagingSelection}
      />
    </>
  );
}
