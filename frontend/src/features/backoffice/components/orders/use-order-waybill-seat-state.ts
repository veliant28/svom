import { useEffect, useMemo, type Dispatch, type MutableRefObject, type SetStateAction } from "react";

import {
  normalizeSeatOptionPayload,
  parsePositiveNumber,
  resolveSeatOptionFromPayload,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type {
  WaybillFormPayload,
  WaybillSeatOptionPayload,
} from "@/features/backoffice/lib/orders/waybill-form";
import type { BackofficeNovaPoshtaLookupPackaging } from "@/features/backoffice/types/nova-poshta.types";

export function useOrderWaybillSeatState({
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
}: {
  isOpen: boolean;
  payload: WaybillFormPayload;
  selectedSeatIndex: number;
  setSelectedSeatIndex: Dispatch<SetStateAction<number>>;
  setPackagingWidth: Dispatch<SetStateAction<string>>;
  setPackagingLength: Dispatch<SetStateAction<string>>;
  setPackagingHeight: Dispatch<SetStateAction<string>>;
  setIsPackagingEnabled: Dispatch<SetStateAction<boolean>>;
  isSeatListMode: boolean;
  seatListButtonsRef: MutableRefObject<Array<HTMLButtonElement | null>>;
  packings: BackofficeNovaPoshtaLookupPackaging[];
}): {
  seatOptions: WaybillSeatOptionPayload[];
  visiblePackings: BackofficeNovaPoshtaLookupPackaging[];
  selectedPackRefs: string[];
  selectedPackingsDisplay: string;
  hasSelectedPackings: boolean;
} {
  const seatOptions = useMemo(() => {
    const fallback = resolveSeatOptionFromPayload(payload);
    const sourceSeats = Array.isArray(payload.options_seat) && payload.options_seat.length > 0
      ? payload.options_seat
      : [fallback];
    return sourceSeats.map((seat) => normalizeSeatOptionPayload(seat, fallback));
  }, [payload]);

  useEffect(() => {
    if (!isOpen || seatOptions.length === 0) {
      return;
    }
    if (selectedSeatIndex > seatOptions.length - 1) {
      setSelectedSeatIndex(seatOptions.length - 1);
      return;
    }
    const activeSeat = seatOptions[selectedSeatIndex] || seatOptions[0];
    if (!activeSeat) {
      return;
    }
    setPackagingWidth(activeSeat.volumetric_width || "20");
    setPackagingLength(activeSeat.volumetric_length || "20");
    setPackagingHeight(activeSeat.volumetric_height || "10");
    setIsPackagingEnabled(
      parsePositiveNumber(activeSeat.volumetric_width || "") > 0
      || parsePositiveNumber(activeSeat.volumetric_length || "") > 0
      || parsePositiveNumber(activeSeat.volumetric_height || "") > 0,
    );
  }, [
    isOpen,
    seatOptions,
    selectedSeatIndex,
    setIsPackagingEnabled,
    setPackagingHeight,
    setPackagingLength,
    setPackagingWidth,
    setSelectedSeatIndex,
  ]);

  useEffect(() => {
    if (!isOpen || !isSeatListMode) {
      return;
    }
    const target = seatListButtonsRef.current[selectedSeatIndex] || seatListButtonsRef.current[0];
    target?.focus();
  }, [isOpen, isSeatListMode, seatListButtonsRef, seatOptions.length, selectedSeatIndex]);

  const visiblePackings = useMemo(() => packings, [packings]);
  const selectedPackRefs = useMemo(() => {
    const activeSeat = seatOptions[selectedSeatIndex] || seatOptions[0];
    if (!activeSeat) {
      return [];
    }
    const explicitRefs = Array.isArray(activeSeat.pack_refs)
      ? activeSeat.pack_refs.map((ref) => String(ref || "").trim()).filter(Boolean)
      : [];
    if (explicitRefs.length > 0) {
      return explicitRefs;
    }
    const legacyRef = (activeSeat.pack_ref || "").trim();
    return legacyRef ? [legacyRef] : [];
  }, [seatOptions, selectedSeatIndex]);
  const selectedPackingsDisplay = useMemo(() => {
    if (!selectedPackRefs.length) {
      return "";
    }
    const labelByRef = new Map(packings.map((item) => [item.ref, (item.label || "").trim() || item.ref]));
    return selectedPackRefs.map((ref) => labelByRef.get(ref) || ref).join(", ");
  }, [packings, selectedPackRefs]);

  return {
    seatOptions,
    visiblePackings,
    selectedPackRefs,
    selectedPackingsDisplay,
    hasSelectedPackings: selectedPackRefs.length > 0,
  };
}
