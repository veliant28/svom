import { useEffect, type Dispatch, type SetStateAction } from "react";

import {
  lookupBackofficeNovaPoshtaDeliveryDate,
  lookupBackofficeNovaPoshtaPackings,
  lookupBackofficeNovaPoshtaTimeIntervals,
} from "@/features/backoffice/api/orders-api";
import {
  formatVolumeDisplay,
  parsePositiveNumber,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type { WaybillFormPayload } from "@/features/backoffice/lib/orders/waybill-form";
import type {
  BackofficeNovaPoshtaLookupDeliveryDate,
  BackofficeNovaPoshtaLookupPackaging,
  BackofficeNovaPoshtaLookupTimeInterval,
} from "@/features/backoffice/types/nova-poshta.types";

export function useOrderWaybillServiceEffects({
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
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    if (!isPackagingEnabled) {
      setPayload((prev) => (prev.volume_general ? { ...prev, volume_general: "" } : prev));
      return;
    }
    const width = parsePositiveNumber(packagingWidth);
    const length = parsePositiveNumber(packagingLength);
    const height = parsePositiveNumber(packagingHeight);
    if (width <= 0 || length <= 0 || height <= 0) {
      setPayload((prev) => (prev.volume_general ? { ...prev, volume_general: "" } : prev));
      return;
    }
    const volumeGeneral = formatVolumeDisplay(Math.max(0.0004, (width * length * height) / 1_000_000));
    setPayload((prev) => (prev.volume_general === volumeGeneral ? prev : { ...prev, volume_general: volumeGeneral }));
  }, [isOpen, isPackagingEnabled, packagingHeight, packagingLength, packagingWidth, setPayload]);

  useEffect(() => {
    if (!isOpen || !isPackagingMode || !token || !payload.sender_profile_id) {
      setPackings([]);
      setPackingsLoading(false);
      return;
    }

    const widthCm = parsePositiveNumber(packagingWidth);
    const lengthCm = parsePositiveNumber(packagingLength);
    const heightCm = parsePositiveNumber(packagingHeight);
    const hasValidDimensions = widthCm > 0 && lengthCm > 0 && heightCm > 0;
    const widthMm = hasValidDimensions ? Math.max(1, Math.round(widthCm * 10)) : undefined;
    const lengthMm = hasValidDimensions ? Math.max(1, Math.round(lengthCm * 10)) : undefined;
    const heightMm = hasValidDimensions ? Math.max(1, Math.round(heightCm * 10)) : undefined;

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPackingsLoading(true);
      try {
        const response = await lookupBackofficeNovaPoshtaPackings(token, {
          sender_profile_id: payload.sender_profile_id,
          length_mm: lengthMm,
          width_mm: widthMm,
          height_mm: heightMm,
          locale,
        });
        if (!cancelled) {
          setPackings(response.results);
        }
      } catch {
        if (!cancelled) {
          setPackings([]);
        }
      } finally {
        if (!cancelled) {
          setPackingsLoading(false);
        }
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    isOpen,
    isPackagingMode,
    locale,
    packagingHeight,
    packagingLength,
    packagingWidth,
    payload.sender_profile_id,
    setPackings,
    setPackingsLoading,
    token,
  ]);

  useEffect(() => {
    if (!isOpen || !isAdditionalServicesMode || !token || !payload.sender_profile_id || !payload.recipient_city_ref) {
      setDeliveryDateLookup(null);
      setDeliveryDateLookupLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setDeliveryDateLookupLoading(true);
      try {
        const response = await lookupBackofficeNovaPoshtaDeliveryDate(token, {
          sender_profile_id: payload.sender_profile_id,
          recipient_city_ref: payload.recipient_city_ref,
          delivery_type: payload.delivery_type,
          date_time: normalizedPreferredDeliveryDate || undefined,
        });
        if (!cancelled) {
          const result = response.result;
          setDeliveryDateLookup(result);
          if ((payload.preferred_delivery_date || "").trim() === "" && result.date) {
            setPayload((prev) => ({ ...prev, preferred_delivery_date: result.date }));
          }
        }
      } catch {
        if (!cancelled) {
          setDeliveryDateLookup(null);
        }
      } finally {
        if (!cancelled) {
          setDeliveryDateLookupLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    isAdditionalServicesMode,
    isOpen,
    normalizedPreferredDeliveryDate,
    payload.delivery_type,
    payload.preferred_delivery_date,
    payload.recipient_city_ref,
    payload.sender_profile_id,
    setDeliveryDateLookup,
    setDeliveryDateLookupLoading,
    setPayload,
    token,
  ]);

  useEffect(() => {
    if (!isOpen || !isAdditionalServicesMode || !token || !payload.sender_profile_id || !payload.recipient_city_ref) {
      setTimeIntervals([]);
      setTimeIntervalsLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setTimeIntervalsLoading(true);
      try {
        const response = await lookupBackofficeNovaPoshtaTimeIntervals(token, {
          sender_profile_id: payload.sender_profile_id,
          recipient_city_ref: payload.recipient_city_ref,
          date_time: normalizedPreferredDeliveryDate || undefined,
        });
        if (!cancelled) {
          setTimeIntervals(response.results);
        }
      } catch {
        if (!cancelled) {
          setTimeIntervals([]);
        }
      } finally {
        if (!cancelled) {
          setTimeIntervalsLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    isAdditionalServicesMode,
    isOpen,
    normalizedPreferredDeliveryDate,
    payload.recipient_city_ref,
    payload.sender_profile_id,
    setTimeIntervals,
    setTimeIntervalsLoading,
    token,
  ]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const currentValue = (payload.time_interval || "").trim();
    if (!currentValue) {
      return;
    }
    if (!payload.recipient_city_ref) {
      setPayload((prev) => ({ ...prev, time_interval: "" }));
      return;
    }
    if (timeIntervalsLoading) {
      return;
    }
    const isCurrentStillAvailable = timeIntervals.some((item) => item.number === currentValue);
    if (isCurrentStillAvailable) {
      return;
    }
    setPayload((prev) => (prev.time_interval ? { ...prev, time_interval: "" } : prev));
  }, [
    isOpen,
    payload.recipient_city_ref,
    payload.time_interval,
    setPayload,
    timeIntervals,
    timeIntervalsLoading,
  ]);
}
