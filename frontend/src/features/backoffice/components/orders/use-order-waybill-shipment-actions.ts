import { type Dispatch, type SetStateAction } from "react";

import {
  buildWaybillSavePayload,
  formatDimensionCmFromMm,
  formatKgDisplay,
  normalizeSeatOptionPayload,
  parsePositiveNumber,
  resolveSeatOptionFromPayload,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type {
  WaybillFormPayload,
  WaybillSeatOptionPayload,
} from "@/features/backoffice/lib/orders/waybill-form";
import type {
  BackofficeNovaPoshtaLookupPackaging,
  BackofficeOrderNovaPoshtaWaybill,
} from "@/features/backoffice/types/nova-poshta.types";

export function useOrderWaybillShipmentActions({
  payload,
  setPayload,
  waybill,
  seatOptions,
  selectedSeatIndex,
  selectedPackRefs,
  normalizedPreferredDeliveryDate,
  packagingWidth,
  packagingLength,
  packagingHeight,
  normalizedSeatsAmount,
  setSelectedSeatIndex,
  setPackagingWidth,
  setPackagingLength,
  setPackagingHeight,
  setIsPackagingEnabled,
  setIsSeatListMode,
  setIsPackagingMode,
  setPackingsDropdownOpen,
  setSeatMenuOpen,
}: {
  payload: WaybillFormPayload;
  setPayload: Dispatch<SetStateAction<WaybillFormPayload>>;
  waybill: BackofficeOrderNovaPoshtaWaybill | null;
  seatOptions: WaybillSeatOptionPayload[];
  selectedSeatIndex: number;
  selectedPackRefs: string[];
  normalizedPreferredDeliveryDate: string;
  packagingWidth: string;
  packagingLength: string;
  packagingHeight: string;
  normalizedSeatsAmount: number;
  setSelectedSeatIndex: Dispatch<SetStateAction<number>>;
  setPackagingWidth: Dispatch<SetStateAction<string>>;
  setPackagingLength: Dispatch<SetStateAction<string>>;
  setPackagingHeight: Dispatch<SetStateAction<string>>;
  setIsPackagingEnabled: Dispatch<SetStateAction<boolean>>;
  setIsSeatListMode: Dispatch<SetStateAction<boolean>>;
  setIsPackagingMode: Dispatch<SetStateAction<boolean>>;
  setPackingsDropdownOpen: Dispatch<SetStateAction<boolean>>;
  setSeatMenuOpen: Dispatch<SetStateAction<boolean>>;
}) {
  const activeSeat = seatOptions[selectedSeatIndex] || seatOptions[0] || resolveSeatOptionFromPayload(payload);
  const cargoTypeUi = (activeSeat.cargo_type || payload.cargo_type || waybill?.cargo_type || "Parcel") as "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels";
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

  return {
    activeSeat,
    cargoTypeUi,
    volumetricWeight,
    payloadForSave: buildWaybillSavePayload({
      payload,
      seatOptions,
      selectedSeatIndex,
      activeSeat,
      packagingWidth,
      packagingLength,
      packagingHeight,
      normalizedPreferredDeliveryDate,
    }),
    updateSeatOptions,
    applyCargoTypeSelection,
    enterPackagingMode,
    leavePackagingMode,
    enterSeatListMode,
    openSeatForEditing,
    addSeat,
    removeSeat,
    togglePackagingSelection,
  };
}
