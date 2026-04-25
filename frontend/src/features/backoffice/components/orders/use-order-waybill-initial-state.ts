import { useEffect, type Dispatch, type MutableRefObject, type SetStateAction } from "react";

import {
  formatKgDisplay,
  normalizeSeatOptionPayload,
  parsePositiveNumber,
  resolveSeatOptionFromPayload,
  type Translator,
  type WaybillAddressSuggestion,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import {
  buildWaybillInitialPayload,
  type WaybillFormPayload,
} from "@/features/backoffice/lib/orders/waybill-form";
import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupDeliveryDate,
  BackofficeNovaPoshtaLookupPackaging,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
  BackofficeNovaPoshtaLookupTimeInterval,
  BackofficeOrderNovaPoshtaWaybill,
} from "@/features/backoffice/types/nova-poshta.types";

export function useOrderWaybillInitialState({
  isOpen,
  order,
  waybill,
  defaultSenderId,
  privateCounterpartyLabel,
  t,
  skipNextRecipientCounterpartyLookupRef,
  setPayload,
  setRecipientCounterpartyQuery,
  setRecipientCounterpartyTypeLabel,
  setRecipientCounterpartyTypeRaw,
  setRecipientCounterparties,
  setActiveRecipientCounterpartyIndex,
  setCityQuery,
  setCityLookupInteracted,
  setSelectedSettlementRef,
  setWarehouseQuery,
  setStreetQuery,
  setSettlements,
  setWarehouses,
  setStreets,
  setPackings,
  setTimeIntervals,
  setDeliveryDateLookup,
  setPackingsLoading,
  setTimeIntervalsLoading,
  setDeliveryDateLookupLoading,
  setActiveSettlementIndex,
  setActiveStreetIndex,
  setActiveWarehouseIndex,
  setSenderMenuOpen,
  setSeatMenuOpen,
  setSelectedSeatIndex,
  setIsSeatListMode,
  setPackagingWidth,
  setPackagingLength,
  setPackagingHeight,
  setIsPackagingMode,
  setIsAdditionalServicesMode,
  setPackingsDropdownOpen,
  setIsPackagingEnabled,
}: {
  isOpen: boolean;
  order: BackofficeOrderOperational | null;
  waybill: BackofficeOrderNovaPoshtaWaybill | null;
  defaultSenderId: string;
  privateCounterpartyLabel: string;
  t: Translator;
  skipNextRecipientCounterpartyLookupRef: MutableRefObject<boolean>;
  setPayload: Dispatch<SetStateAction<WaybillFormPayload>>;
  setRecipientCounterpartyQuery: Dispatch<SetStateAction<string>>;
  setRecipientCounterpartyTypeLabel: Dispatch<SetStateAction<string>>;
  setRecipientCounterpartyTypeRaw: Dispatch<SetStateAction<string>>;
  setRecipientCounterparties: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupCounterparty[]>>;
  setActiveRecipientCounterpartyIndex: Dispatch<SetStateAction<number>>;
  setCityQuery: Dispatch<SetStateAction<string>>;
  setCityLookupInteracted: Dispatch<SetStateAction<boolean>>;
  setSelectedSettlementRef: Dispatch<SetStateAction<string>>;
  setWarehouseQuery: Dispatch<SetStateAction<string>>;
  setStreetQuery: Dispatch<SetStateAction<string>>;
  setSettlements: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setWarehouses: Dispatch<SetStateAction<WaybillAddressSuggestion[]>>;
  setStreets: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupStreet[]>>;
  setPackings: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupPackaging[]>>;
  setTimeIntervals: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupTimeInterval[]>>;
  setDeliveryDateLookup: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupDeliveryDate | null>>;
  setPackingsLoading: Dispatch<SetStateAction<boolean>>;
  setTimeIntervalsLoading: Dispatch<SetStateAction<boolean>>;
  setDeliveryDateLookupLoading: Dispatch<SetStateAction<boolean>>;
  setActiveSettlementIndex: Dispatch<SetStateAction<number>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
  setSenderMenuOpen: Dispatch<SetStateAction<boolean>>;
  setSeatMenuOpen: Dispatch<SetStateAction<boolean>>;
  setSelectedSeatIndex: Dispatch<SetStateAction<number>>;
  setIsSeatListMode: Dispatch<SetStateAction<boolean>>;
  setPackagingWidth: Dispatch<SetStateAction<string>>;
  setPackagingLength: Dispatch<SetStateAction<string>>;
  setPackagingHeight: Dispatch<SetStateAction<string>>;
  setIsPackagingMode: Dispatch<SetStateAction<boolean>>;
  setIsAdditionalServicesMode: Dispatch<SetStateAction<boolean>>;
  setPackingsDropdownOpen: Dispatch<SetStateAction<boolean>>;
  setIsPackagingEnabled: Dispatch<SetStateAction<boolean>>;
}) {
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const initialPayload = buildWaybillInitialPayload(order, waybill, defaultSenderId);
    const fallbackSeat = resolveSeatOptionFromPayload(initialPayload);
    const initialSeats = Array.isArray(initialPayload.options_seat) && initialPayload.options_seat.length > 0
      ? initialPayload.options_seat.map((seat) => normalizeSeatOptionPayload(seat, fallbackSeat))
      : [fallbackSeat];
    const firstSeat = initialSeats[0] || fallbackSeat;
    setPayload({
      ...initialPayload,
      description: (initialPayload.description || "").trim() || t("orders.modals.waybill.auto.descriptionValue"),
      weight: formatKgDisplay(initialPayload.weight),
      seats_amount: initialSeats.length,
      options_seat: initialSeats,
    });
    const hasRecipientCounterpartyRef = Boolean((waybill?.recipient_counterparty_ref || "").trim());
    const nextCounterpartyQuery = hasRecipientCounterpartyRef
      ? (waybill?.recipient_name ?? "")
      : privateCounterpartyLabel;
    skipNextRecipientCounterpartyLookupRef.current = true;
    setRecipientCounterpartyQuery(nextCounterpartyQuery);
    if (hasRecipientCounterpartyRef) {
      setRecipientCounterpartyTypeLabel("");
      setRecipientCounterpartyTypeRaw("");
    } else {
      setRecipientCounterpartyTypeLabel(privateCounterpartyLabel);
      setRecipientCounterpartyTypeRaw("PrivatePerson");
    }
    setRecipientCounterparties([]);
    setActiveRecipientCounterpartyIndex(-1);
    setCityQuery(initialPayload.recipient_city_label || "");
    setCityLookupInteracted(false);
    setSelectedSettlementRef(initialPayload.recipient_city_ref || "");
    setWarehouseQuery(initialPayload.recipient_address_label || "");
    setStreetQuery(initialPayload.recipient_street_label || "");
    setSettlements([]);
    setWarehouses([]);
    setStreets([]);
    setPackings([]);
    setTimeIntervals([]);
    setDeliveryDateLookup(null);
    setPackingsLoading(false);
    setTimeIntervalsLoading(false);
    setDeliveryDateLookupLoading(false);
    setActiveSettlementIndex(-1);
    setActiveStreetIndex(-1);
    setActiveWarehouseIndex(-1);
    setSenderMenuOpen(false);
    setSeatMenuOpen(false);
    setSelectedSeatIndex(0);
    setIsSeatListMode(false);
    setPackagingWidth(firstSeat.volumetric_width || "20");
    setPackagingLength(firstSeat.volumetric_length || "20");
    setPackagingHeight(firstSeat.volumetric_height || "10");
    setIsPackagingMode(false);
    setIsAdditionalServicesMode(false);
    setPackingsDropdownOpen(false);
    setIsPackagingEnabled(
      parsePositiveNumber(firstSeat.volumetric_width || "") > 0
      || parsePositiveNumber(firstSeat.volumetric_length || "") > 0
      || parsePositiveNumber(firstSeat.volumetric_height || "") > 0,
    );
  }, [
    defaultSenderId,
    isOpen,
    order,
    privateCounterpartyLabel,
    setActiveRecipientCounterpartyIndex,
    setActiveSettlementIndex,
    setActiveStreetIndex,
    setActiveWarehouseIndex,
    setCityLookupInteracted,
    setCityQuery,
    setDeliveryDateLookup,
    setDeliveryDateLookupLoading,
    setIsAdditionalServicesMode,
    setIsPackagingEnabled,
    setIsPackagingMode,
    setIsSeatListMode,
    setPackagingHeight,
    setPackagingLength,
    setPackagingWidth,
    setPackings,
    setPackingsDropdownOpen,
    setPackingsLoading,
    setPayload,
    setRecipientCounterparties,
    setRecipientCounterpartyQuery,
    setRecipientCounterpartyTypeLabel,
    setRecipientCounterpartyTypeRaw,
    setSelectedSeatIndex,
    setSelectedSettlementRef,
    setSenderMenuOpen,
    setSeatMenuOpen,
    setSettlements,
    setStreetQuery,
    setStreets,
    setTimeIntervals,
    setTimeIntervalsLoading,
    setWarehouseQuery,
    setWarehouses,
    skipNextRecipientCounterpartyLookupRef,
    t,
    waybill,
  ]);
}
