import { useEffect, useMemo, useRef, useState } from "react";
import { OrderWaybillTrackingModal } from "@/features/backoffice/components/orders/order-waybill-tracking-modal";
import { OrderWaybillDropdownPortals } from "@/features/backoffice/components/orders/order-waybill-dropdown-portals";
import { OrderWaybillFooter } from "@/features/backoffice/components/orders/order-waybill-footer";
import { OrderWaybillPaymentAdditionalSection } from "@/features/backoffice/components/orders/order-waybill-payment-additional-section";
import { OrderWaybillModalHeader } from "@/features/backoffice/components/orders/order-waybill-modal-header";
import { OrderWaybillRecipientSection } from "@/features/backoffice/components/orders/order-waybill-recipient-section";
import { OrderWaybillSenderSection } from "@/features/backoffice/components/orders/order-waybill-sender-section";
import { OrderWaybillShipmentSection } from "@/features/backoffice/components/orders/order-waybill-shipment-section";
import { useOrderWaybillAddressSelection } from "@/features/backoffice/components/orders/use-order-waybill-address-selection";
import { useOrderWaybillFloatingDropdowns } from "@/features/backoffice/components/orders/use-order-waybill-floating-dropdowns";
import { useOrderWaybillInitialState } from "@/features/backoffice/components/orders/use-order-waybill-initial-state";
import { useOrderWaybillLookupEffects } from "@/features/backoffice/components/orders/use-order-waybill-lookup-effects";
import { useOrderWaybillOutsideClick } from "@/features/backoffice/components/orders/use-order-waybill-outside-click";
import { useOrderWaybillPaymentState } from "@/features/backoffice/components/orders/use-order-waybill-payment-state";
import { useOrderWaybillRecipientCounterpartySelection } from "@/features/backoffice/components/orders/use-order-waybill-recipient-counterparty-selection";
import { useOrderWaybillSeatState } from "@/features/backoffice/components/orders/use-order-waybill-seat-state";
import {
  buildWaybillSavePayload,
  formatDimensionCmFromMm,
  formatKgDisplay,
  normalizePreferredDeliveryDate,
  normalizeSeatOptionPayload,
  parsePositiveNumber,
  resolveSeatOptionFromPayload,
  type Translator,
  type WaybillAddressSuggestion,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import {
  getSenderMetaLabel,
  normalizeCounterpartyType,
  resolveTimeIntervalFallbackLabel,
} from "@/features/backoffice/components/orders/order-waybill-party.helpers";
import {
  buildWaybillInitialPayload,
  type WaybillSeatOptionPayload,
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
  BackofficeNovaPoshtaSenderProfile,
  BackofficeOrderNovaPoshtaWaybill,
} from "@/features/backoffice/types/nova-poshta.types";

export function OrderWaybillModal({
  isOpen,
  token,
  locale,
  order,
  waybill,
  senderProfiles,
  isLoading,
  isSubmitting,
  isSyncing,
  isDeleting,
  onRefresh,
  onSave,
  onSync,
  onDelete,
  onPrint,
  onClose,
  t,
}: {
  isOpen: boolean;
  token: string | null;
  locale: string;
  order: BackofficeOrderOperational | null;
  waybill: BackofficeOrderNovaPoshtaWaybill | null;
  senderProfiles: BackofficeNovaPoshtaSenderProfile[];
  isLoading: boolean;
  isSubmitting: boolean;
  isSyncing: boolean;
  isDeleting: boolean;
  onRefresh: () => void;
  onSave: (payload: WaybillFormPayload) => void;
  onSync: () => void;
  onDelete: () => void;
  onPrint: (format: "html" | "pdf") => void;
  onClose: () => void;
  t: Translator;
}) {
  const defaultSenderId = useMemo(() => {
    const sender =
      senderProfiles.find((item) => item.is_default && item.is_active)
      || senderProfiles.find((item) => item.is_active)
      || senderProfiles.find((item) => item.is_default)
      || senderProfiles[0];
    return sender?.id ?? "";
  }, [senderProfiles]);
  const [payload, setPayload] = useState<WaybillFormPayload>(() => {
    const initialPayload = buildWaybillInitialPayload(order, waybill, defaultSenderId);
    return {
      ...initialPayload,
      weight: formatKgDisplay(initialPayload.weight),
    };
  });
  const [recipientCounterpartyQuery, setRecipientCounterpartyQuery] = useState("");
  const [recipientCounterpartyTypeLabel, setRecipientCounterpartyTypeLabel] = useState("");
  const [recipientCounterpartyTypeRaw, setRecipientCounterpartyTypeRaw] = useState("");
  const [recipientCounterparties, setRecipientCounterparties] = useState<BackofficeNovaPoshtaLookupCounterparty[]>([]);
  const [recipientCounterpartyLoading, setRecipientCounterpartyLoading] = useState(false);
  const [activeRecipientCounterpartyIndex, setActiveRecipientCounterpartyIndex] = useState(-1);
  const [cityQuery, setCityQuery] = useState("");
  const [cityLookupInteracted, setCityLookupInteracted] = useState(false);
  const [selectedSettlementRef, setSelectedSettlementRef] = useState("");
  const [settlements, setSettlements] = useState<BackofficeNovaPoshtaLookupSettlement[]>([]);
  const [settlementLoading, setSettlementLoading] = useState(false);
  const [activeSettlementIndex, setActiveSettlementIndex] = useState(-1);
  const [warehouseQuery, setWarehouseQuery] = useState("");
  const [warehouses, setWarehouses] = useState<WaybillAddressSuggestion[]>([]);
  const [warehouseLoading, setWarehouseLoading] = useState(false);
  const [activeWarehouseIndex, setActiveWarehouseIndex] = useState(-1);
  const [streetQuery, setStreetQuery] = useState("");
  const [streets, setStreets] = useState<BackofficeNovaPoshtaLookupStreet[]>([]);
  const [streetLoading, setStreetLoading] = useState(false);
  const [activeStreetIndex, setActiveStreetIndex] = useState(-1);
  const [packings, setPackings] = useState<BackofficeNovaPoshtaLookupPackaging[]>([]);
  const [packingsLoading, setPackingsLoading] = useState(false);
  const [timeIntervals, setTimeIntervals] = useState<BackofficeNovaPoshtaLookupTimeInterval[]>([]);
  const [timeIntervalsLoading, setTimeIntervalsLoading] = useState(false);
  const [trackingModalOpen, setTrackingModalOpen] = useState(false);
  const [deliveryDateLookup, setDeliveryDateLookup] = useState<BackofficeNovaPoshtaLookupDeliveryDate | null>(null);
  const [deliveryDateLookupLoading, setDeliveryDateLookupLoading] = useState(false);
  const [senderMenuOpen, setSenderMenuOpen] = useState(false);
  const [seatMenuOpen, setSeatMenuOpen] = useState(false);
  const [isSeatListMode, setIsSeatListMode] = useState(false);
  const [selectedSeatIndex, setSelectedSeatIndex] = useState(0);
  const [packagingWidth, setPackagingWidth] = useState("20");
  const [packagingLength, setPackagingLength] = useState("20");
  const [packagingHeight, setPackagingHeight] = useState("10");
  const [isPackagingMode, setIsPackagingMode] = useState(false);
  const [isAdditionalServicesMode, setIsAdditionalServicesMode] = useState(false);
  const [packingsDropdownOpen, setPackingsDropdownOpen] = useState(false);
  const [isPackagingEnabled, setIsPackagingEnabled] = useState(false);
  const recipientCounterpartyDetailsRequestRef = useRef(0);
  const skipNextRecipientCounterpartyLookupRef = useRef(false);
  const skipNextSettlementLookupRef = useRef(false);
  const skipNextStreetLookupRef = useRef(false);
  const skipNextWarehouseLookupRef = useRef(false);
  const senderMenuRef = useRef<HTMLDivElement | null>(null);
  const seatMenuRef = useRef<HTMLDivElement | null>(null);
  const contentScrollRef = useRef<HTMLDivElement | null>(null);
  const recipientCounterpartyLookupRootRef = useRef<HTMLLabelElement | null>(null);
  const cityLookupRootRef = useRef<HTMLLabelElement | null>(null);
  const streetLookupRootRef = useRef<HTMLLabelElement | null>(null);
  const warehouseLookupRootRef = useRef<HTMLLabelElement | null>(null);
  const packingsLookupRootRef = useRef<HTMLLabelElement | null>(null);
  const recipientCounterpartyInputRef = useRef<HTMLInputElement | null>(null);
  const cityInputRef = useRef<HTMLInputElement | null>(null);
  const streetInputRef = useRef<HTMLInputElement | null>(null);
  const warehouseInputRef = useRef<HTMLInputElement | null>(null);
  const packingsInputRef = useRef<HTMLInputElement | null>(null);
  const seatListButtonsRef = useRef<Array<HTMLButtonElement | null>>([]);
  const recipientCounterpartyDropdownRef = useRef<HTMLDivElement | null>(null);
  const cityDropdownRef = useRef<HTMLDivElement | null>(null);
  const streetDropdownRef = useRef<HTMLDivElement | null>(null);
  const warehouseDropdownRef = useRef<HTMLDivElement | null>(null);
  const packingsDropdownRef = useRef<HTMLDivElement | null>(null);
  const sender = useMemo(
    () => senderProfiles.find((item) => item.id === payload.sender_profile_id),
    [payload.sender_profile_id, senderProfiles],
  );
  const recipientCounterpartyType = normalizeCounterpartyType(recipientCounterpartyTypeRaw);
  const recipientHasSelectedCounterparty = Boolean((payload.recipient_counterparty_ref || "").trim());
  const recipientIsPrivatePerson = !recipientHasSelectedCounterparty || recipientCounterpartyType === "private_person";
  const privateCounterpartyLabel = t("orders.modals.waybill.meta.senderTypes.privatePerson");
  const normalizedPreferredDeliveryDate = normalizePreferredDeliveryDate(payload.preferred_delivery_date || "");
  const preferredDeliveryDateInvalid = Boolean(payload.preferred_delivery_date) && !normalizedPreferredDeliveryDate;
  const isBusy = isLoading || isSubmitting || isSyncing || isDeleting;
  const isReadonlyDocument = Boolean(waybill && !waybill.can_edit);
  const formDisabled = isBusy || isReadonlyDocument;
  const {
    nonCashSupported,
    thirdPersonSupported,
    payerTypeUi,
    paymentMethodUi,
    paymentAmountFieldLabel,
    paymentValidationMessage,
    canSubmit,
  } = useOrderWaybillPaymentState({
    isOpen,
    payload,
    setPayload,
    sender,
    waybill,
    recipientIsPrivatePerson,
    formDisabled,
    preferredDeliveryDateInvalid,
    t,
  });

  useOrderWaybillInitialState({
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
  });

  useOrderWaybillOutsideClick({
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
  });

  useOrderWaybillLookupEffects({
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
  });

  const {
    seatOptions,
    visiblePackings,
    selectedPackRefs,
    selectedPackingsDisplay,
    hasSelectedPackings,
  } = useOrderWaybillSeatState({
    isOpen,
    payload,
    selectedSeatIndex,
    setSelectedSeatIndex,
    setPackagingWidth,
    setPackagingLength,
    setPackagingHeight,
    setIsPackagingEnabled,
    isSeatListMode,
    seatListButtonsRef,
    packings,
  });
  const {
    recipientCounterpartyDropdownStyle,
    cityDropdownStyle,
    streetDropdownStyle,
    warehouseDropdownStyle,
    packingsDropdownStyle,
  } = useOrderWaybillFloatingDropdowns({
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
    recipientCounterpartiesCount: recipientCounterparties.length,
    activeRecipientCounterpartyIndex,
    cityLookupInteracted,
    settlementLoading,
    settlementsCount: settlements.length,
    activeSettlementIndex,
    streetLoading,
    streetsCount: streets.length,
    activeStreetIndex,
    warehouseLoading,
    warehousesCount: warehouses.length,
    activeWarehouseIndex,
    isPackagingMode,
    packingsDropdownOpen,
    packingsLoading,
    visiblePackingsCount: visiblePackings.length,
  });
  const timeIntervalOptions = useMemo(
    () => timeIntervals.map((item) => {
      const timeLabel = (item.label || "").trim();
      const label = timeLabel && timeLabel !== item.number
        ? timeLabel
        : resolveTimeIntervalFallbackLabel(item.number, t);
      return {
        value: item.number,
        label,
      };
    }),
    [t, timeIntervals],
  );
  useEffect(() => {
    if (!isOpen) {
      setTrackingModalOpen(false);
    }
  }, [isOpen]);

  const applyRecipientCounterpartySelection = useOrderWaybillRecipientCounterpartySelection({
    token,
    locale,
    senderProfileId: payload.sender_profile_id,
    recipientCounterpartyDetailsRequestRef,
    skipNextRecipientCounterpartyLookupRef,
    skipNextSettlementLookupRef,
    setPayload,
    setRecipientCounterpartyQuery,
    setRecipientCounterpartyTypeLabel,
    setRecipientCounterpartyTypeRaw,
    setRecipientCounterparties,
    setActiveRecipientCounterpartyIndex,
    setSelectedSettlementRef,
    setCityLookupInteracted,
    setCityQuery,
    setStreetQuery,
    setStreets,
    setActiveStreetIndex,
    setWarehouseQuery,
    setWarehouses,
    setActiveWarehouseIndex,
  });
  const {
    applySettlementSelection,
    applyStreetSelection,
    applyWarehouseSuggestionSelection,
  } = useOrderWaybillAddressSelection({
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
  });

  if (!isOpen) {
    return null;
  }

  const senderCounterpartyDisplay = getSenderMetaLabel(sender, "counterparty_label");
  const senderCityDisplay = getSenderMetaLabel(sender, "city_label");
  const senderAddressDisplay = getSenderMetaLabel(sender, "address_label");
  const activeSeat = seatOptions[selectedSeatIndex] || seatOptions[0] || resolveSeatOptionFromPayload(payload);
  const cargoTypeUi = (activeSeat.cargo_type || payload.cargo_type || waybill?.cargo_type || "Parcel") as "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels";
  const handleTrackWaybill = async () => {
    if (!waybill) {
      return;
    }
    setTrackingModalOpen(true);
    await onSync();
  };
  const normalizedSeatsAmount = Math.max(1, seatOptions.length || payload.seats_amount || 1);
  const width = parsePositiveNumber(packagingWidth);
  const length = parsePositiveNumber(packagingLength);
  const height = parsePositiveNumber(packagingHeight);
  const volumetricWeight =
    width <= 0 || length <= 0 || height <= 0
      ? formatKgDisplay(activeSeat.weight || payload.weight || "0")
      : formatKgDisplay((width * length * height) / 4000);
  const updateSeatOptions = (
    updater: (seats: WaybillSeatOptionPayload[], activeIndex: number) => WaybillSeatOptionPayload[],
  ) => {
    setPayload((prev) => {
      const fallback = resolveSeatOptionFromPayload(prev);
      const currentSeats = Array.isArray(prev.options_seat) && prev.options_seat.length > 0
        ? prev.options_seat.map((seat) => normalizeSeatOptionPayload(seat, fallback))
        : [fallback];
      const activeIndex = Math.min(Math.max(0, selectedSeatIndex), Math.max(0, currentSeats.length - 1));
      const nextSeatsRaw = updater(currentSeats, activeIndex);
      const nextSeats = nextSeatsRaw.length > 0
        ? nextSeatsRaw.map((seat) => normalizeSeatOptionPayload(seat, fallback))
        : [fallback];
      return {
        ...prev,
        seats_amount: nextSeats.length,
        options_seat: nextSeats,
      };
    });
  };
  const applyCargoTypeSelection = (nextType: "Cargo" | "Parcel" | "Documents" | "Pallet") => {
    updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
      index === activeIndex
        ? { ...seat, cargo_type: nextType }
        : seat
    )));
    setPayload((prev) => ({ ...prev, cargo_type: nextType }));
  };
  const applyPayerTypeSelection = (nextType: "Sender" | "Recipient" | "ThirdPerson") => {
    if (nextType === "ThirdPerson" && !thirdPersonSupported) {
      return;
    }
    setPayload((prev) => ({
      ...prev,
      payer_type: nextType,
      payment_method: nextType === "ThirdPerson"
        ? "NonCash"
        : (nextType === "Recipient" && recipientIsPrivatePerson)
          ? "Cash"
        : ((prev.payment_method as "Cash" | "NonCash" | undefined) || "Cash"),
    }));
  };
  const applyPaymentMethodSelection = (nextMethod: "Cash" | "NonCash") => {
    if (nextMethod === "NonCash" && !nonCashSupported) {
      return;
    }
    setPayload((prev) => {
      if ((prev.payer_type || "Recipient") === "Recipient" && recipientIsPrivatePerson && nextMethod === "NonCash") {
        return { ...prev, payment_method: "Cash" };
      }
      if ((prev.payer_type || "Recipient") === "ThirdPerson" && nextMethod === "Cash") {
        return { ...prev, payment_method: "NonCash" };
      }
      return { ...prev, payment_method: nextMethod };
    });
  };
  const enterPackagingMode = () => {
    setIsSeatListMode(false);
    setIsPackagingMode(true);
    setPackingsDropdownOpen(true);
    setSeatMenuOpen(false);
  };
  const leavePackagingMode = () => {
    setIsPackagingMode(false);
    setPackingsDropdownOpen(false);
    setSeatMenuOpen(false);
  };
  const enterAdditionalServicesMode = () => {
    setIsAdditionalServicesMode(true);
  };
  const leaveAdditionalServicesMode = () => {
    setIsAdditionalServicesMode(false);
  };
  const enterSeatListMode = () => {
    if (normalizedSeatsAmount <= 1) {
      return;
    }
    setIsPackagingMode(false);
    setPackingsDropdownOpen(false);
    setIsSeatListMode(true);
    setSeatMenuOpen(false);
  };
  const openSeatForEditing = (index: number) => {
    setSelectedSeatIndex(Math.max(0, Math.min(index, Math.max(0, seatOptions.length - 1))));
    setIsSeatListMode(false);
    setIsPackagingMode(false);
    setPackingsDropdownOpen(false);
    setSeatMenuOpen(false);
  };
  const addSeat = () => {
    let nextIndex = selectedSeatIndex;
    updateSeatOptions((seats, activeIndex) => {
      const baseSeat = seats[activeIndex] || seats[0] || resolveSeatOptionFromPayload(payload);
      const nextSeat: WaybillSeatOptionPayload = {
        ...baseSeat,
      };
      const nextSeats = [
        ...seats.slice(0, activeIndex + 1),
        nextSeat,
        ...seats.slice(activeIndex + 1),
      ];
      nextIndex = activeIndex + 1;
      return nextSeats;
    });
    setSelectedSeatIndex(nextIndex);
    setSeatMenuOpen(false);
  };
  const removeSeat = () => {
    if (normalizedSeatsAmount <= 1) {
      return;
    }
    let nextIndex = selectedSeatIndex;
    updateSeatOptions((seats, activeIndex) => {
      if (seats.length <= 1) {
        return seats;
      }
      const nextSeats = seats.filter((_, index) => index !== activeIndex);
      nextIndex = Math.max(0, Math.min(activeIndex, nextSeats.length - 1));
      return nextSeats;
    });
    setSelectedSeatIndex(nextIndex);
    setIsSeatListMode(false);
    setSeatMenuOpen(false);
  };
  const togglePackagingSelection = (packing: BackofficeNovaPoshtaLookupPackaging) => {
    const normalizedRef = (packing.ref || "").trim();
    if (!normalizedRef) {
      return;
    }
    const hasRef = selectedPackRefs.includes(normalizedRef);
    const nextRefs = hasRef
      ? selectedPackRefs.filter((ref) => ref !== normalizedRef)
      : [...selectedPackRefs, normalizedRef];
    updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
      index === activeIndex
        ? {
          ...seat,
          pack_refs: nextRefs,
          pack_ref: nextRefs[0] || "",
        }
        : seat
    )));
    const nextWidth = formatDimensionCmFromMm(packing.width_mm);
    const nextLength = formatDimensionCmFromMm(packing.length_mm);
    const nextHeight = formatDimensionCmFromMm(packing.height_mm);
    if (nextWidth) {
      setPackagingWidth(nextWidth);
    }
    if (nextLength) {
      setPackagingLength(nextLength);
    }
    if (nextHeight) {
      setPackagingHeight(nextHeight);
    }
    if (nextWidth || nextLength || nextHeight) {
      setIsPackagingEnabled(true);
      updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
        index === activeIndex
          ? {
            ...seat,
            volumetric_width: nextWidth || seat.volumetric_width || "",
            volumetric_length: nextLength || seat.volumetric_length || "",
            volumetric_height: nextHeight || seat.volumetric_height || "",
          }
          : seat
      )));
    }
    setPackingsDropdownOpen(false);
  };
  const payloadForSave = buildWaybillSavePayload({
    payload,
    seatOptions,
    selectedSeatIndex,
    activeSeat,
    packagingWidth,
    packagingLength,
    packagingHeight,
    normalizedPreferredDeliveryDate,
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
      <button type="button" className="absolute inset-0 bg-black/40" aria-label={t("orders.actions.closeModal")} onClick={onClose} />
      <div
        className="relative z-10 flex max-h-[94vh] w-[96vw] max-w-[1600px] flex-col overflow-hidden rounded-md border"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <OrderWaybillModalHeader waybill={waybill} t={t} onClose={onClose} />
        <div ref={contentScrollRef} className="flex-1 min-h-0 overflow-y-auto p-4">
          <div className="grid items-stretch gap-3 xl:grid-cols-4">
            <OrderWaybillSenderSection
              senderMenuRef={senderMenuRef}
              senderMenuOpen={senderMenuOpen}
              senderProfiles={senderProfiles}
              sender={sender}
              senderCounterpartyDisplay={senderCounterpartyDisplay}
              senderCityDisplay={senderCityDisplay}
              senderAddressDisplay={senderAddressDisplay}
              formDisabled={formDisabled}
              t={t}
              setSenderMenuOpen={setSenderMenuOpen}
              setPayload={setPayload}
            />
            {!isAdditionalServicesMode ? (
              <OrderWaybillRecipientSection
                recipientCounterpartyLookupRootRef={recipientCounterpartyLookupRootRef}
                recipientCounterpartyInputRef={recipientCounterpartyInputRef}
                cityLookupRootRef={cityLookupRootRef}
                cityInputRef={cityInputRef}
                warehouseLookupRootRef={warehouseLookupRootRef}
                warehouseInputRef={warehouseInputRef}
                skipNextRecipientCounterpartyLookupRef={skipNextRecipientCounterpartyLookupRef}
                payload={payload}
                recipientCounterpartyQuery={recipientCounterpartyQuery}
                recipientCounterpartyTypeLabel={recipientCounterpartyTypeLabel}
                recipientCounterpartyLoading={recipientCounterpartyLoading}
                recipientIsPrivatePerson={recipientIsPrivatePerson}
                privateCounterpartyLabel={privateCounterpartyLabel}
                recipientCounterparties={recipientCounterparties}
                activeRecipientCounterpartyIndex={activeRecipientCounterpartyIndex}
                cityQuery={cityQuery}
                settlements={settlements}
                activeSettlementIndex={activeSettlementIndex}
                warehouseQuery={warehouseQuery}
                warehouses={warehouses}
                activeWarehouseIndex={activeWarehouseIndex}
                warehouseLoading={warehouseLoading}
                formDisabled={formDisabled}
                t={t}
                setPayload={setPayload}
                setRecipientCounterpartyTypeLabel={setRecipientCounterpartyTypeLabel}
                setRecipientCounterpartyTypeRaw={setRecipientCounterpartyTypeRaw}
                setRecipientCounterpartyQuery={setRecipientCounterpartyQuery}
                setRecipientCounterparties={setRecipientCounterparties}
                setActiveRecipientCounterpartyIndex={setActiveRecipientCounterpartyIndex}
                setCityLookupInteracted={setCityLookupInteracted}
                setSelectedSettlementRef={setSelectedSettlementRef}
                setCityQuery={setCityQuery}
                setSettlements={setSettlements}
                setActiveSettlementIndex={setActiveSettlementIndex}
                setStreets={setStreets}
                setActiveStreetIndex={setActiveStreetIndex}
                setWarehouses={setWarehouses}
                setActiveWarehouseIndex={setActiveWarehouseIndex}
                setWarehouseQuery={setWarehouseQuery}
                applyRecipientCounterpartySelection={applyRecipientCounterpartySelection}
                applySettlementSelection={applySettlementSelection}
                applyWarehouseSuggestionSelection={applyWarehouseSuggestionSelection}
              />
            ) : null}

            <OrderWaybillShipmentSection
              seatMenuRef={seatMenuRef}
              seatListButtonsRef={seatListButtonsRef}
              packingsLookupRootRef={packingsLookupRootRef}
              packingsInputRef={packingsInputRef}
              isPackagingMode={isPackagingMode}
              isSeatListMode={isSeatListMode}
              seatMenuOpen={seatMenuOpen}
              selectedSeatIndex={selectedSeatIndex}
              normalizedSeatsAmount={normalizedSeatsAmount}
              seatOptions={seatOptions}
              activeSeat={activeSeat}
              selectedPackingsDisplay={selectedPackingsDisplay}
              packingsLoading={packingsLoading}
              visiblePackings={visiblePackings}
              hasSelectedPackings={hasSelectedPackings}
              packagingWidth={packagingWidth}
              packagingLength={packagingLength}
              packagingHeight={packagingHeight}
              volumetricWeight={volumetricWeight}
              cargoTypeUi={cargoTypeUi}
              formDisabled={formDisabled}
              t={t}
              setIsSeatListMode={setIsSeatListMode}
              setSeatMenuOpen={setSeatMenuOpen}
              setSelectedSeatIndex={setSelectedSeatIndex}
              setPackingsDropdownOpen={setPackingsDropdownOpen}
              setPackagingWidth={setPackagingWidth}
              setPackagingLength={setPackagingLength}
              setPackagingHeight={setPackagingHeight}
              setIsPackagingEnabled={setIsPackagingEnabled}
              leavePackagingMode={leavePackagingMode}
              addSeat={addSeat}
              removeSeat={removeSeat}
              enterSeatListMode={enterSeatListMode}
              openSeatForEditing={openSeatForEditing}
              updateSeatOptions={updateSeatOptions}
              enterPackagingMode={enterPackagingMode}
              applyCargoTypeSelection={applyCargoTypeSelection}
            />

            <OrderWaybillPaymentAdditionalSection
              isAdditionalServicesMode={isAdditionalServicesMode}
              formDisabled={formDisabled}
              payload={payload}
              currency={order?.currency || ""}
              paymentAmountFieldLabel={paymentAmountFieldLabel}
              payerTypeUi={payerTypeUi}
              paymentMethodUi={paymentMethodUi}
              thirdPersonSupported={thirdPersonSupported}
              recipientIsPrivatePerson={recipientIsPrivatePerson}
              nonCashSupported={nonCashSupported}
              paymentValidationMessage={paymentValidationMessage}
              preferredDeliveryDateInvalid={preferredDeliveryDateInvalid}
              deliveryDateLookupLoading={deliveryDateLookupLoading}
              deliveryDateLookup={deliveryDateLookup}
              timeIntervalsLoading={timeIntervalsLoading}
              timeIntervalOptions={timeIntervalOptions}
              syncError={waybill?.last_sync_error || ""}
              t={t}
              setPayload={setPayload}
              applyPayerTypeSelection={applyPayerTypeSelection}
              applyPaymentMethodSelection={applyPaymentMethodSelection}
              enterAdditionalServicesMode={enterAdditionalServicesMode}
              leaveAdditionalServicesMode={leaveAdditionalServicesMode}
            />
          </div>
        </div>

        <OrderWaybillDropdownPortals
          cityDropdownRef={cityDropdownRef}
          cityDropdownStyle={cityDropdownStyle}
          settlementLoading={settlementLoading}
          settlements={settlements}
          activeSettlementIndex={activeSettlementIndex}
          recipientCounterpartyDropdownRef={recipientCounterpartyDropdownRef}
          recipientCounterpartyDropdownStyle={recipientCounterpartyDropdownStyle}
          recipientCounterpartyLoading={recipientCounterpartyLoading}
          recipientCounterparties={recipientCounterparties}
          activeRecipientCounterpartyIndex={activeRecipientCounterpartyIndex}
          streetDropdownRef={streetDropdownRef}
          streetDropdownStyle={streetDropdownStyle}
          streetLoading={streetLoading}
          streets={streets}
          activeStreetIndex={activeStreetIndex}
          warehouseDropdownRef={warehouseDropdownRef}
          warehouseDropdownStyle={warehouseDropdownStyle}
          warehouseLoading={warehouseLoading}
          warehouses={warehouses}
          activeWarehouseIndex={activeWarehouseIndex}
          packingsDropdownRef={packingsDropdownRef}
          packingsDropdownStyle={packingsDropdownStyle}
          packingsLoading={packingsLoading}
          visiblePackings={visiblePackings}
          selectedPackRefs={selectedPackRefs}
          t={t}
          setActiveSettlementIndex={setActiveSettlementIndex}
          applySettlementSelection={applySettlementSelection}
          setActiveRecipientCounterpartyIndex={setActiveRecipientCounterpartyIndex}
          applyRecipientCounterpartySelection={applyRecipientCounterpartySelection}
          setActiveStreetIndex={setActiveStreetIndex}
          applyStreetSelection={applyStreetSelection}
          setActiveWarehouseIndex={setActiveWarehouseIndex}
          applyWarehouseSuggestionSelection={applyWarehouseSuggestionSelection}
          togglePackagingSelection={togglePackagingSelection}
        />

        <OrderWaybillFooter
          waybill={waybill}
          isBusy={isBusy}
          isSubmitting={isSubmitting}
          canSubmit={canSubmit}
          isReadonlyDocument={isReadonlyDocument}
          payloadForSave={payloadForSave}
          t={t}
          onDelete={onDelete}
          onRefresh={onRefresh}
          onTrack={handleTrackWaybill}
          onPrint={onPrint}
          onSave={onSave}
        />
      </div>
      <OrderWaybillTrackingModal
        isOpen={trackingModalOpen}
        waybill={waybill}
        locale={locale}
        t={t}
        onClose={() => setTrackingModalOpen(false)}
      />
    </div>
  );
}
