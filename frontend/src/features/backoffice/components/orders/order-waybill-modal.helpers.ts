import type { CSSProperties } from "react";

import type {
  WaybillFormPayload,
  WaybillSeatOptionPayload,
} from "@/features/backoffice/lib/orders/waybill-form";
import type {
  BackofficeNovaPoshtaLookupWarehouse,
} from "@/features/backoffice/types/nova-poshta.types";

export type Translator = (key: string, values?: Record<string, string | number>) => string;

export type WaybillAddressSuggestion = {
  kind: "warehouse" | "street";
  ref: string;
  label: string;
  subtitle: string;
  selectedLabel?: string;
  settlementRef?: string;
};

export const LETTER_QUERY_WAREHOUSE_LIMIT = 8;

const WAYBILL_CARGO_TYPES = new Set(["Cargo", "Parcel", "Documents", "Pallet", "TiresWheels"]);

export function formatKgDisplay(value: number | string | null | undefined): string {
  if (value === null || value === undefined) {
    return "0";
  }

  const numericValue = typeof value === "number" ? value : Number(String(value).trim().replace(",", "."));

  if (!Number.isFinite(numericValue)) {
    return String(value);
  }

  return numericValue.toFixed(3).replace(/\.?0+$/, "");
}

export function parsePositiveNumber(value: string): number {
  const normalized = Number(String(value).trim().replace(",", "."));
  if (!Number.isFinite(normalized) || normalized <= 0) {
    return 0;
  }
  return normalized;
}

export function formatVolumeDisplay(value: number): string {
  return value.toFixed(4).replace(/\.?0+$/, "");
}

export function formatDimensionCmFromMm(value: string): string {
  const numeric = Number(String(value || "").trim().replace(",", "."));
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "";
  }
  return (numeric / 10).toFixed(1).replace(/\.?0+$/, "");
}

export function resolveSeatOptionFromPayload(payload: WaybillFormPayload): WaybillSeatOptionPayload {
  const explicitRefs = Array.isArray(payload.pack_refs)
    ? payload.pack_refs.map((ref) => String(ref || "").trim()).filter(Boolean)
    : [];
  const fallbackRef = (payload.pack_ref || "").trim();
  const packRefs = explicitRefs.length ? explicitRefs : (fallbackRef ? [fallbackRef] : []);
  const cargoType = String(payload.cargo_type || "").trim();
  return {
    description: (payload.description || "").trim(),
    cost: String(payload.cost || "").trim() || "0",
    weight: String(payload.weight || "").trim() || "0.001",
    pack_ref: packRefs[0] || "",
    pack_refs: packRefs,
    volumetric_width: String(payload.volumetric_width || "").trim(),
    volumetric_length: String(payload.volumetric_length || "").trim(),
    volumetric_height: String(payload.volumetric_height || "").trim(),
    volumetric_volume: String(payload.volume_general || "").trim(),
    cargo_type: (WAYBILL_CARGO_TYPES.has(cargoType) ? cargoType : "Parcel") as WaybillSeatOptionPayload["cargo_type"],
    special_cargo: Boolean(payload.special_cargo),
  };
}

export function buildWaybillSavePayload({
  payload,
  seatOptions,
  selectedSeatIndex,
  activeSeat,
  packagingWidth,
  packagingLength,
  packagingHeight,
  normalizedPreferredDeliveryDate,
}: {
  payload: WaybillFormPayload;
  seatOptions: WaybillSeatOptionPayload[];
  selectedSeatIndex: number;
  activeSeat: WaybillSeatOptionPayload;
  packagingWidth: string;
  packagingLength: string;
  packagingHeight: string;
  normalizedPreferredDeliveryDate: string;
}): WaybillFormPayload {
  const normalizedSeatPayloads = seatOptions.map((seat) => {
    const refs = Array.isArray(seat.pack_refs)
      ? seat.pack_refs.map((ref) => String(ref || "").trim()).filter(Boolean)
      : [];
    const packRef = refs[0] || String(seat.pack_ref || "").trim();
    return {
      ...seat,
      description: String(seat.description || "").trim(),
      cost: String(seat.cost || "").trim() || "0",
      weight: String(seat.weight || "").trim() || "0.001",
      pack_ref: packRef,
      pack_refs: refs.length ? refs : (packRef ? [packRef] : []),
      volumetric_width: String(seat.volumetric_width || "").trim(),
      volumetric_length: String(seat.volumetric_length || "").trim(),
      volumetric_height: String(seat.volumetric_height || "").trim(),
      volumetric_volume: String(seat.volumetric_volume || "").trim(),
      cargo_type: (seat.cargo_type || "Parcel") as WaybillSeatOptionPayload["cargo_type"],
      special_cargo: Boolean(seat.special_cargo || payload.special_cargo),
    } as WaybillSeatOptionPayload;
  });
  const activeSeatForSave = normalizedSeatPayloads[selectedSeatIndex] || normalizedSeatPayloads[0] || activeSeat;
  const aggregatedSeatWeight = normalizedSeatPayloads.reduce(
    (sum, seat) => sum + parsePositiveNumber(seat.weight || "0"),
    0,
  );
  const aggregatedSeatCost = normalizedSeatPayloads.reduce(
    (sum, seat) => sum + parsePositiveNumber(seat.cost || "0"),
    0,
  );
  const aggregatedSeatDescription = normalizedSeatPayloads.find((seat) => seat.description)?.description
    || (payload.description || "");
  const aggregatedSeatRefs = Array.from(new Set(
    normalizedSeatPayloads.flatMap((seat) => (
      Array.isArray(seat.pack_refs) && seat.pack_refs.length
        ? seat.pack_refs
        : (seat.pack_ref ? [seat.pack_ref] : [])
    )),
  ));
  return {
    ...payload,
    seats_amount: normalizedSeatPayloads.length,
    cargo_type: (activeSeatForSave?.cargo_type || payload.cargo_type || "Parcel") as WaybillFormPayload["cargo_type"],
    description: aggregatedSeatDescription,
    weight: aggregatedSeatWeight > 0 ? formatKgDisplay(aggregatedSeatWeight) : formatKgDisplay(payload.weight),
    cost: aggregatedSeatCost > 0 ? String(aggregatedSeatCost.toFixed(2)).replace(/\.?0+$/, "") : payload.cost,
    pack_refs: aggregatedSeatRefs,
    pack_ref: aggregatedSeatRefs[0] || "",
    preferred_delivery_date: normalizedPreferredDeliveryDate,
    volumetric_width: activeSeatForSave?.volumetric_width || packagingWidth,
    volumetric_length: activeSeatForSave?.volumetric_length || packagingLength,
    volumetric_height: activeSeatForSave?.volumetric_height || packagingHeight,
    volume_general: activeSeatForSave?.volumetric_volume || payload.volume_general,
    options_seat: normalizedSeatPayloads.map((seat) => {
      const seatPayload: WaybillSeatOptionPayload = {
        description: seat.description || "",
        cost: seat.cost || "0",
        weight: seat.weight || "0.001",
        cargo_type: seat.cargo_type || "Parcel",
        special_cargo: Boolean(seat.special_cargo),
      };
      if (seat.pack_ref) {
        seatPayload.pack_ref = seat.pack_ref;
      }
      if (Array.isArray(seat.pack_refs) && seat.pack_refs.length) {
        seatPayload.pack_refs = seat.pack_refs;
      }
      if ((seat.volumetric_width || "").trim()) {
        seatPayload.volumetric_width = seat.volumetric_width;
      }
      if ((seat.volumetric_length || "").trim()) {
        seatPayload.volumetric_length = seat.volumetric_length;
      }
      if ((seat.volumetric_height || "").trim()) {
        seatPayload.volumetric_height = seat.volumetric_height;
      }
      if ((seat.volumetric_volume || "").trim()) {
        seatPayload.volumetric_volume = seat.volumetric_volume;
      }
      return seatPayload;
    }),
  };
}

export function normalizeSeatOptionPayload(
  seat: WaybillSeatOptionPayload | null | undefined,
  fallback: WaybillSeatOptionPayload,
): WaybillSeatOptionPayload {
  const refs = Array.isArray(seat?.pack_refs)
    ? seat?.pack_refs?.map((ref) => String(ref || "").trim()).filter(Boolean)
    : [];
  const seatPackRef = String(seat?.pack_ref || "").trim();
  const packRefs = refs.length ? refs : (seatPackRef ? [seatPackRef] : []);
  const cargoType = String(seat?.cargo_type || "").trim();
  return {
    description: String(seat?.description || "").trim() || fallback.description || "",
    cost: String(seat?.cost || "").trim() || fallback.cost || "0",
    weight: String(seat?.weight || "").trim() || fallback.weight || "0.001",
    pack_ref: packRefs[0] || "",
    pack_refs: packRefs,
    volumetric_width: String(seat?.volumetric_width || "").trim(),
    volumetric_length: String(seat?.volumetric_length || "").trim(),
    volumetric_height: String(seat?.volumetric_height || "").trim(),
    volumetric_volume: String(seat?.volumetric_volume || "").trim(),
    cargo_type: (
      WAYBILL_CARGO_TYPES.has(cargoType)
        ? cargoType
        : (fallback.cargo_type || "Parcel")
    ) as WaybillSeatOptionPayload["cargo_type"],
    special_cargo: seat?.special_cargo ?? fallback.special_cargo ?? false,
  };
}

export function formatPreferredDeliveryDateInput(value: string): string {
  const digitsOnly = String(value || "").replace(/\D/g, "").slice(0, 8);
  if (digitsOnly.length <= 2) {
    return digitsOnly;
  }
  if (digitsOnly.length <= 4) {
    return `${digitsOnly.slice(0, 2)}.${digitsOnly.slice(2)}`;
  }
  return `${digitsOnly.slice(0, 2)}.${digitsOnly.slice(2, 4)}.${digitsOnly.slice(4)}`;
}

export function normalizePreferredDeliveryDate(value: string): string {
  const normalized = String(value || "").trim();
  if (!/^\d{2}\.\d{2}\.\d{4}$/.test(normalized)) {
    return "";
  }
  const [dayRaw, monthRaw, yearRaw] = normalized.split(".");
  const day = Number(dayRaw);
  const month = Number(monthRaw);
  const year = Number(yearRaw);
  if (!Number.isInteger(day) || !Number.isInteger(month) || !Number.isInteger(year)) {
    return "";
  }
  if (month < 1 || month > 12 || day < 1 || day > 31 || year < 2000 || year > 2100) {
    return "";
  }
  const date = new Date(year, month - 1, day);
  if (
    date.getFullYear() !== year
    || date.getMonth() !== month - 1
    || date.getDate() !== day
  ) {
    return "";
  }
  return `${String(day).padStart(2, "0")}.${String(month).padStart(2, "0")}.${String(year).padStart(4, "0")}`;
}

export function scrollDropdownOptionIntoView(
  root: HTMLElement | null,
  scope: string,
  index: number,
) {
  if (!root || index < 0) {
    return;
  }
  const option = root.querySelector<HTMLElement>(`[data-nav-scope="${scope}"][data-nav-index="${index}"]`);
  if (!option) {
    return;
  }
  const list = option.parentElement as HTMLElement | null;
  if (!list) {
    return;
  }
  const optionTop = option.offsetTop;
  const optionBottom = optionTop + option.offsetHeight;
  const viewTop = list.scrollTop;
  const viewBottom = viewTop + list.clientHeight;
  if (optionTop < viewTop) {
    list.scrollTop = optionTop;
    return;
  }
  if (optionBottom > viewBottom) {
    list.scrollTop = optionBottom - list.clientHeight;
  }
}

export function computeFloatingDropdownStyle(
  input: HTMLInputElement | null,
  options?: { maxHeight?: number },
): CSSProperties | null {
  if (!input || typeof window === "undefined") {
    return null;
  }
  const rect = input.getBoundingClientRect();
  const viewportPadding = 8;
  const left = Math.max(viewportPadding, Math.min(rect.left, window.innerWidth - viewportPadding - rect.width));
  const top = Math.min(rect.bottom + 4, window.innerHeight - 84);
  const availableBelow = Math.max(80, window.innerHeight - top - viewportPadding);
  return {
    position: "fixed",
    left,
    top,
    width: rect.width,
    maxHeight: Math.min(options?.maxHeight ?? 176, availableBelow),
    zIndex: 1400,
  };
}

export function formatWarehouseLookupDisplay(item: BackofficeNovaPoshtaLookupWarehouse): { label: string; subtitle: string } {
  const normalizedNumber = String(item.number || "").trim();
  const normalizedDescription = String(item.description || item.full_description || "").trim();
  const descriptionPrefix = normalizedDescription.includes(":")
    ? normalizedDescription.split(":")[0].trim()
    : normalizedDescription;
  const descriptionTail = normalizedDescription.includes(":")
    ? normalizedDescription.split(":").slice(1).join(":").trim()
    : "";
  const shortWithoutCity = String(item.label || "").split(",").slice(1).join(",").trim();
  const fallbackStreet = shortWithoutCity || descriptionTail || item.ref;
  const normalizedCategory = String(item.category || "").toLowerCase();
  const normalizedType = String(item.type || "").toLowerCase();
  const normalizedText = `${normalizedDescription} ${shortWithoutCity}`.toLowerCase();
  const isPostomat =
    normalizedCategory.includes("postomat")
    || normalizedType.includes("postomat")
    || normalizedType.includes("поштомат")
    || normalizedType.includes("постомат")
    || normalizedText.includes("поштомат")
    || normalizedText.includes("постомат");
  const typeLabel = isPostomat ? "Поштомат" : "Відділення";
  const fallbackLabel = normalizedNumber ? `${typeLabel} №${normalizedNumber}` : typeLabel;
  return {
    label: descriptionPrefix || fallbackLabel,
    subtitle: fallbackStreet,
  };
}

export function formatWarehouseSelectedLabel(item: BackofficeNovaPoshtaLookupWarehouse): string {
  const normalizedDescription = String(item.description || item.full_description || "").trim();
  if (normalizedDescription) {
    return normalizedDescription.replace(/\s*:\s*/g, ", ");
  }
  return String(item.label || "").trim();
}

export function splitAddressInput(value: string): { base: string; suffix: string } {
  const normalized = value.trim();
  if (!normalized) {
    return { base: "", suffix: "" };
  }
  const [basePart, ...suffixParts] = normalized.split(",");
  return {
    base: (basePart || "").trim(),
    suffix: suffixParts.join(",").trim(),
  };
}

export function parseHouseApartmentFromSuffix(suffix: string): { house: string; apartment: string } {
  const normalized = suffix.trim();
  if (!normalized) {
    return { house: "", apartment: "" };
  }
  const slashMatch = normalized.match(/^(.+?)\s*\/\s*(.+)$/);
  if (slashMatch) {
    return { house: slashMatch[1].trim(), apartment: slashMatch[2].trim() };
  }
  const kvMatch = normalized.match(/^(.+?)\s*(?:кв\.?|квартира)\s*(.+)$/i);
  if (kvMatch) {
    return { house: kvMatch[1].trim(), apartment: kvMatch[2].trim() };
  }
  return { house: normalized, apartment: "" };
}
