import {
  AlertCircle,
  ArrowLeft,
  Archive,
  Circle,
  FileText,
  MoreHorizontal,
  ScanBarcode,
  ScanLine,
  Truck,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

import {
  lookupBackofficeNovaPoshtaCounterparties,
  lookupBackofficeNovaPoshtaCounterpartyDetails,
  lookupBackofficeNovaPoshtaDeliveryDate,
  lookupBackofficeNovaPoshtaPackings,
  lookupBackofficeNovaPoshtaSettlements,
  lookupBackofficeNovaPoshtaStreets,
  lookupBackofficeNovaPoshtaTimeIntervals,
  lookupBackofficeNovaPoshtaWarehouses,
} from "@/features/backoffice/api/orders-api";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import {
  buildWaybillInitialPayload,
  canSaveWaybill,
  normalizeWaybillPhone,
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
  BackofficeNovaPoshtaLookupWarehouse,
  BackofficeNovaPoshtaSenderProfile,
  BackofficeOrderNovaPoshtaWaybill,
} from "@/features/backoffice/types/nova-poshta.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;
type WaybillAddressSuggestion = {
  kind: "warehouse" | "street";
  ref: string;
  label: string;
  subtitle: string;
  settlementRef?: string;
};

const LETTER_QUERY_WAREHOUSE_LIMIT = 8;
const DRAFT_SENDER_NAME = "Черновик отправителя";
const WAYBILL_CARGO_TYPES = new Set(["Cargo", "Parcel", "Documents", "Pallet", "TiresWheels"]);

function formatKgDisplay(value: number | string | null | undefined): string {
  if (value === null || value === undefined) {
    return "0";
  }

  const numericValue =
    typeof value === "number" ? value : Number(String(value).trim().replace(",", "."));

  if (!Number.isFinite(numericValue)) {
    return String(value);
  }

  return numericValue.toFixed(3).replace(/\.?0+$/, "");
}

function parsePositiveNumber(value: string): number {
  const normalized = Number(String(value).trim().replace(",", "."));
  if (!Number.isFinite(normalized) || normalized <= 0) {
    return 0;
  }
  return normalized;
}

function formatVolumeDisplay(value: number): string {
  return value.toFixed(4).replace(/\.?0+$/, "");
}

function formatDimensionCmFromMm(value: string): string {
  const numeric = Number(String(value || "").trim().replace(",", "."));
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "";
  }
  return (numeric / 10).toFixed(1).replace(/\.?0+$/, "");
}

function resolveSeatOptionFromPayload(payload: WaybillFormPayload): WaybillSeatOptionPayload {
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

function normalizeSeatOptionPayload(
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

function formatPreferredDeliveryDateInput(value: string): string {
  const digitsOnly = String(value || "").replace(/\D/g, "").slice(0, 8);
  if (digitsOnly.length <= 2) {
    return digitsOnly;
  }
  if (digitsOnly.length <= 4) {
    return `${digitsOnly.slice(0, 2)}.${digitsOnly.slice(2)}`;
  }
  return `${digitsOnly.slice(0, 2)}.${digitsOnly.slice(2, 4)}.${digitsOnly.slice(4)}`;
}

function normalizePreferredDeliveryDate(value: string): string {
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

function scrollDropdownOptionIntoView(
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

function computeFloatingDropdownStyle(
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

function formatWarehouseLookupDisplay(item: BackofficeNovaPoshtaLookupWarehouse): { label: string; subtitle: string } {
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

function splitAddressInput(value: string): { base: string; suffix: string } {
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

function parseHouseApartmentFromSuffix(suffix: string): { house: string; apartment: string } {
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

function normalizeSenderType(value: string | null | undefined): "private_person" | "fop" | "business" | "unknown" {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "unknown";
  }
  const compact = normalized.replace(/[\s_-]+/g, "");
  if (normalized.includes("фоп") || normalized.includes("флп") || compact.includes("fop")) {
    return "fop";
  }
  if (normalized.includes("organization") || normalized.includes("company") || compact.includes("business")) {
    return "business";
  }
  if (compact.includes("privateperson") || compact.includes("privatperson")) {
    return "private_person";
  }
  if (normalized === "private_person") {
    return "private_person";
  }
  if (normalized === "fop") {
    return "fop";
  }
  if (normalized === "business" || normalized === "organization" || normalized === "org" || normalized === "company") {
    return "business";
  }
  return "unknown";
}

function getSenderTypeHint(sender: BackofficeNovaPoshtaSenderProfile | undefined, key: string): string {
  if (!sender || !sender.raw_meta || typeof sender.raw_meta !== "object") {
    return "";
  }
  const value = sender.raw_meta[key];
  return typeof value === "string" ? value.trim() : "";
}

function resolveEffectiveSenderType(
  sender: BackofficeNovaPoshtaSenderProfile | undefined,
  fallbackSenderType?: string,
): "private_person" | "fop" | "business" | "unknown" {
  const candidates = [
    sender?.sender_type || "",
    fallbackSenderType || "",
    getSenderTypeHint(sender, "inferred_sender_type"),
    getSenderTypeHint(sender, "counterparty_type"),
    getSenderTypeHint(sender, "ownership_form_description"),
    getSenderTypeHint(sender, "counterparty_label"),
    sender?.organization_name || "",
    sender?.edrpou || "",
    sender?.name || "",
    sender?.contact_name || "",
  ];

  let hasPrivatePerson = false;
  for (const candidate of candidates) {
    const normalized = normalizeSenderType(candidate);
    if (normalized === "fop" || normalized === "business") {
      return normalized;
    }
    if (normalized === "private_person") {
      hasPrivatePerson = true;
    }
  }
  return hasPrivatePerson ? "private_person" : "unknown";
}

function resolveSenderPreview(): { payer: string; payment: string } {
  return { payer: "Recipient", payment: "Cash" };
}

type SenderPaymentCapabilities = {
  canNonCashPayment: boolean | null;
  canPayThirdPerson: boolean | null;
};

function parseCapabilityBoolean(value: unknown): boolean | null {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true" || normalized === "1") {
      return true;
    }
    if (normalized === "false" || normalized === "0") {
      return false;
    }
  }
  return null;
}

function resolveSenderPaymentCapabilities(
  sender: BackofficeNovaPoshtaSenderProfile | undefined,
): SenderPaymentCapabilities {
  if (!sender) {
    return {
      canNonCashPayment: null,
      canPayThirdPerson: null,
    };
  }

  const meta = sender.raw_meta && typeof sender.raw_meta === "object" ? sender.raw_meta : {};
  const validationPayload = sender.last_validation_payload && typeof sender.last_validation_payload === "object"
    ? sender.last_validation_payload
    : {};
  const validationPayloadMap = validationPayload as Record<string, unknown>;
  const validationData = Array.isArray(validationPayloadMap.data)
    ? (validationPayloadMap.data as Record<string, unknown>[])
    : [];
  const firstValidationData = validationData[0];
  const options = (
    firstValidationData && typeof firstValidationData === "object"
      ? firstValidationData
      : (validationPayloadMap.options && typeof validationPayloadMap.options === "object")
        ? validationPayloadMap.options
        : {}
  ) as Record<string, unknown>;
  const normalizedMeta = meta as Record<string, unknown>;

  const canNonCashPayment = parseCapabilityBoolean(
    options.CanNonCashPayment ?? normalizedMeta.CanNonCashPayment ?? normalizedMeta.can_non_cash_payment,
  );
  const canPayThirdPerson = parseCapabilityBoolean(
    options.CanPayTheThirdPerson ?? normalizedMeta.CanPayTheThirdPerson ?? normalizedMeta.can_pay_the_third_person,
  );

  return {
    canNonCashPayment,
    canPayThirdPerson,
  };
}

function resolveSenderDisplayName(sender: BackofficeNovaPoshtaSenderProfile | undefined): string {
  if (!sender) {
    return "—";
  }
  const normalizedName = (sender.name || "").trim();
  if (normalizedName && normalizedName !== DRAFT_SENDER_NAME) {
    return normalizedName;
  }
  return (sender.contact_name || "").trim()
    || (sender.phone || "").trim()
    || (sender.counterparty_ref || "").trim()
    || "—";
}

function isSenderRefLike(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) {
    return false;
  }
  if (/^pending-[\w-]+$/i.test(normalized)) {
    return true;
  }
  return /^[0-9A-Za-z]{8}-[0-9A-Za-z]{4}-[0-9A-Za-z]{4}-[0-9A-Za-z]{4}-[0-9A-Za-z]{12}$/.test(normalized);
}

function resolveCounterpartyTypeDisplay(rawValue: string): string {
  const normalized = rawValue.trim();
  if (!normalized) {
    return "";
  }
  const compact = normalized.toLowerCase().replace(/[\s_-]+/g, "");
  if (compact === "privateperson" || compact === "privatperson") {
    return "Частное лицо";
  }
  return normalized;
}

function normalizeCounterpartyType(rawValue: string | null | undefined): "private_person" | "fop" | "business" | "unknown" {
  const normalized = String(rawValue || "").trim().toLowerCase();
  if (!normalized) {
    return "unknown";
  }
  const compact = normalized.replace(/[\s_-]+/g, "");
  if (
    compact.includes("privateperson")
    || compact.includes("privatperson")
    || normalized.includes("приват")
    || normalized.includes("фізич")
    || normalized.includes("частн")
  ) {
    return "private_person";
  }
  if (compact.includes("fop") || normalized.includes("фоп") || normalized.includes("флп")) {
    return "fop";
  }
  if (
    compact.includes("business")
    || compact.includes("organization")
    || compact.includes("legalentity")
    || normalized.includes("організац")
    || normalized.includes("юрид")
    || normalized.includes("бізнес")
  ) {
    return "business";
  }
  return "unknown";
}

function normalizeCounterpartyBusinessCode(rawValue: string): string {
  return String(rawValue || "").replace(/\D+/g, "");
}

function isCounterpartyBusinessCodeQuery(rawValue: string): boolean {
  const code = normalizeCounterpartyBusinessCode(rawValue);
  return code.length === 8 || code.length === 10;
}

function getSenderMetaLabel(sender: BackofficeNovaPoshtaSenderProfile | undefined, key: string): string {
  if (!sender || !sender.raw_meta || typeof sender.raw_meta !== "object") {
    return "";
  }
  const value = sender.raw_meta[key];
  if (typeof value !== "string") {
    return "";
  }
  const normalized = value.trim();
  if (!normalized || isSenderRefLike(normalized)) {
    return "";
  }
  return normalized;
}

function resolvePayerTypeLabel(value: "Sender" | "Recipient" | "ThirdPerson", t: Translator): string {
  if (value === "Sender") {
    return t("orders.modals.waybill.meta.payerTypes.sender");
  }
  if (value === "ThirdPerson") {
    return t("orders.modals.waybill.meta.payerTypes.thirdPerson");
  }
  return t("orders.modals.waybill.meta.payerTypes.recipient");
}

function resolvePaymentMethodLabel(value: "Cash" | "NonCash", t: Translator): string {
  if (value === "NonCash") {
    return t("orders.modals.waybill.meta.paymentMethods.nonCash");
  }
  return t("orders.modals.waybill.meta.paymentMethods.cash");
}

function resolveTimeIntervalFallbackLabel(number: string, t: Translator): string {
  if (number === "CityDeliveryTimeInterval1") {
    return t("orders.modals.waybill.additional.timeInterval1");
  }
  if (number === "CityDeliveryTimeInterval2") {
    return t("orders.modals.waybill.additional.timeInterval2");
  }
  if (number === "CityDeliveryTimeInterval3") {
    return t("orders.modals.waybill.additional.timeInterval3");
  }
  if (number === "CityDeliveryTimeInterval4") {
    return t("orders.modals.waybill.additional.timeInterval4");
  }
  return number;
}

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
    const sender = senderProfiles.find((item) => item.is_default) || senderProfiles[0];
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
  const [, setFloatingTick] = useState(0);
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
  const senderPaymentCapabilities = useMemo(
    () => resolveSenderPaymentCapabilities(sender),
    [sender],
  );
  const effectiveSenderType = resolveEffectiveSenderType(sender, waybill?.sender_profile_type || "");
  const senderRequiresControlPayment = effectiveSenderType === "fop" || effectiveSenderType === "business";
  const recipientCounterpartyType = normalizeCounterpartyType(recipientCounterpartyTypeRaw);
  const recipientHasSelectedCounterparty = Boolean((payload.recipient_counterparty_ref || "").trim());
  const recipientIsPrivatePerson = !recipientHasSelectedCounterparty || recipientCounterpartyType === "private_person";
  const privateCounterpartyLabel = t("orders.modals.waybill.meta.senderTypes.privatePerson");
  const nonCashSupported = senderPaymentCapabilities.canNonCashPayment !== false;
  const thirdPersonSupported = senderPaymentCapabilities.canPayThirdPerson !== false && nonCashSupported;
  const normalizedPreferredDeliveryDate = normalizePreferredDeliveryDate(payload.preferred_delivery_date || "");
  const preferredDeliveryDateInvalid = Boolean(payload.preferred_delivery_date) && !normalizedPreferredDeliveryDate;

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
  }, [defaultSenderId, isOpen, order, privateCounterpartyLabel, t, waybill]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setPayload((prev) => {
      let nextPayerType = (prev.payer_type || "Recipient") as "Sender" | "Recipient" | "ThirdPerson";
      let nextPaymentMethod = (prev.payment_method || "Cash") as "Cash" | "NonCash";

      if (nextPayerType === "ThirdPerson" && !thirdPersonSupported) {
        nextPayerType = "Recipient";
      }
      if (nextPayerType === "ThirdPerson" && nextPaymentMethod !== "NonCash") {
        nextPaymentMethod = "NonCash";
      }
      if (nextPayerType === "Recipient" && recipientIsPrivatePerson && nextPaymentMethod === "NonCash") {
        nextPaymentMethod = "Cash";
      }
      if (nextPaymentMethod === "NonCash" && !nonCashSupported) {
        nextPaymentMethod = "Cash";
      }

      if (nextPayerType === prev.payer_type && nextPaymentMethod === prev.payment_method) {
        return prev;
      }
      return {
        ...prev,
        payer_type: nextPayerType,
        payment_method: nextPaymentMethod,
      };
    });
  }, [isOpen, nonCashSupported, recipientIsPrivatePerson, senderRequiresControlPayment, thirdPersonSupported]);

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
  }, [isOpen, isPackagingEnabled, packagingHeight, packagingLength, packagingWidth]);

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
  }, [isOpen]);

  useEffect(() => {
    const hasAnyFloatingDropdown = (
      recipientCounterparties.length > 0
      || settlements.length > 0
      || streets.length > 0
      || warehouses.length > 0
      || (isPackagingMode && (packingsLoading || packings.length > 0))
    );
    if (
      !isOpen
      || !hasAnyFloatingDropdown
    ) {
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
  }, [isOpen, recipientCounterparties.length, settlements.length, streets.length, warehouses.length, isPackagingMode, packingsLoading, packings.length]);

  useEffect(() => {
    if (!isOpen || !token || !payload.sender_profile_id) {
      setRecipientCounterpartyLoading(false);
      return;
    }
    if (skipNextRecipientCounterpartyLookupRef.current) {
      skipNextRecipientCounterpartyLookupRef.current = false;
      setRecipientCounterpartyLoading(false);
      return;
    }
    const query = recipientCounterpartyQuery.trim();
    if (!query || isSenderRefLike(query) || normalizeCounterpartyType(query) === "private_person") {
      setRecipientCounterparties([]);
      setActiveRecipientCounterpartyIndex(-1);
      setRecipientCounterpartyLoading(false);
      return;
    }
    if (!isCounterpartyBusinessCodeQuery(query)) {
      setRecipientCounterparties([]);
      setActiveRecipientCounterpartyIndex(-1);
      setRecipientCounterpartyLoading(false);
      return;
    }
    const normalizedBusinessCode = normalizeCounterpartyBusinessCode(query);

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setRecipientCounterpartyLoading(true);
      try {
        const response = await lookupBackofficeNovaPoshtaCounterparties(token, {
          sender_profile_id: payload.sender_profile_id,
          query: normalizedBusinessCode,
          counterparty_property: "Recipient",
          locale,
        });
        if (!cancelled) {
          setRecipientCounterparties(response.results);
          setActiveRecipientCounterpartyIndex(response.results.length > 0 ? 0 : -1);
        }
      } catch {
        if (!cancelled) {
          setRecipientCounterparties([]);
          setActiveRecipientCounterpartyIndex(-1);
        }
      } finally {
        if (!cancelled) {
          setRecipientCounterpartyLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [isOpen, locale, payload.sender_profile_id, recipientCounterpartyQuery, token]);

  useEffect(() => {
    if (!isOpen || !token || !payload.sender_profile_id) {
      setSettlementLoading(false);
      return;
    }
    if (skipNextSettlementLookupRef.current) {
      skipNextSettlementLookupRef.current = false;
      setSettlementLoading(false);
      return;
    }
    if (cityQuery.trim().length < 2) {
      setSettlements([]);
      setActiveSettlementIndex(-1);
      setSettlementLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setSettlementLoading(true);
      try {
        const response = await lookupBackofficeNovaPoshtaSettlements(token, {
          sender_profile_id: payload.sender_profile_id,
          query: cityQuery,
          locale,
        });
        if (!cancelled) {
          setSettlements(response.results);
          setActiveSettlementIndex(response.results.length > 0 ? 0 : -1);
        }
      } catch {
        if (!cancelled) {
          setSettlements([]);
          setActiveSettlementIndex(-1);
        }
      } finally {
        if (!cancelled) {
          setSettlementLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [cityQuery, isOpen, locale, payload.sender_profile_id, token]);

  useEffect(() => {
    if (!isOpen || !token || !payload.sender_profile_id || !payload.recipient_city_ref) {
      setWarehouseLoading(false);
      return;
    }
    if (skipNextWarehouseLookupRef.current) {
      skipNextWarehouseLookupRef.current = false;
      setWarehouseLoading(false);
      return;
    }
    const { base: warehouseLookupQuery } = splitAddressInput(warehouseQuery);
    const hasCommaInAddressInput = warehouseQuery.includes(",");
    if (hasCommaInAddressInput) {
      setWarehouses([]);
      setActiveWarehouseIndex(-1);
      setWarehouseLoading(false);
      return;
    }
    const isDigitsOnlyWarehouseQuery = /^\d+$/.test(warehouseLookupQuery);
    const warehouseMinQueryLength = isDigitsOnlyWarehouseQuery ? 1 : 2;
    if (warehouseLookupQuery.length < warehouseMinQueryLength) {
      setWarehouses([]);
      setActiveWarehouseIndex(-1);
      setWarehouseLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setWarehouseLoading(true);
      try {
        const hasLetters = /[A-Za-zА-Яа-яІіЇїЄєҐґ]/.test(warehouseLookupQuery);
        const [warehousesResponse, streetsResponse] = await Promise.all([
          lookupBackofficeNovaPoshtaWarehouses(token, {
            sender_profile_id: payload.sender_profile_id,
            city_ref: payload.recipient_city_ref,
            query: warehouseLookupQuery,
            locale,
          }),
          hasLetters && Boolean(selectedSettlementRef.trim())
            ? lookupBackofficeNovaPoshtaStreets(token, {
              sender_profile_id: payload.sender_profile_id,
              settlement_ref: selectedSettlementRef,
              query: warehouseLookupQuery,
              locale,
            })
            : Promise.resolve({ results: [] as BackofficeNovaPoshtaLookupStreet[] }),
        ]);
        if (!cancelled) {
          const warehouseRows: WaybillAddressSuggestion[] = warehousesResponse.results.map((item) => {
            const formatted = formatWarehouseLookupDisplay(item);
            return {
              kind: "warehouse",
              ref: item.ref,
              label: formatted.label,
              subtitle: formatted.subtitle,
            };
          });
          const streetRows: WaybillAddressSuggestion[] = streetsResponse.results.map((item) => ({
            kind: "street",
            ref: item.street_ref,
            label: item.label || item.street_name || item.street_ref,
            subtitle: "",
            settlementRef: item.settlement_ref,
          }));
          const limitedWarehouseRows = hasLetters
            ? warehouseRows.slice(0, LETTER_QUERY_WAREHOUSE_LIMIT)
            : warehouseRows;
          const merged = hasLetters ? [...streetRows, ...limitedWarehouseRows] : warehouseRows;
          setWarehouses(merged);
          setActiveWarehouseIndex(merged.length > 0 ? 0 : -1);
        }
      } catch {
        if (!cancelled) {
          setWarehouses([]);
          setActiveWarehouseIndex(-1);
        }
      } finally {
        if (!cancelled) {
          setWarehouseLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [isOpen, locale, payload.delivery_type, payload.recipient_city_ref, payload.sender_profile_id, selectedSettlementRef, token, warehouseQuery]);

  useEffect(() => {
    if (!streetInputRef.current || !isOpen || !token || payload.delivery_type !== "address" || !payload.sender_profile_id || !selectedSettlementRef) {
      setStreetLoading(false);
      return;
    }
    if (skipNextStreetLookupRef.current) {
      skipNextStreetLookupRef.current = false;
      setStreetLoading(false);
      return;
    }
    if (streetQuery.trim().length < 2) {
      setStreets([]);
      setActiveStreetIndex(-1);
      setStreetLoading(false);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setStreetLoading(true);
      try {
        const response = await lookupBackofficeNovaPoshtaStreets(token, {
          sender_profile_id: payload.sender_profile_id,
          settlement_ref: selectedSettlementRef,
          query: streetQuery,
          locale,
        });
        if (!cancelled) {
          setStreets(response.results);
          setActiveStreetIndex(response.results.length > 0 ? 0 : -1);
        }
      } catch {
        if (!cancelled) {
          setStreets([]);
          setActiveStreetIndex(-1);
        }
      } finally {
        if (!cancelled) {
          setStreetLoading(false);
        }
      }
    }, 300);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [isOpen, locale, payload.delivery_type, payload.sender_profile_id, selectedSettlementRef, streetQuery, token]);

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
  }, [isOpen, isPackagingMode, locale, packagingHeight, packagingLength, packagingWidth, payload.sender_profile_id, token]);

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
  }, [isAdditionalServicesMode, isOpen, normalizedPreferredDeliveryDate, payload.recipient_city_ref, payload.sender_profile_id, token]);

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
  }, [isAdditionalServicesMode, isOpen, payload.recipient_city_ref, payload.time_interval, timeIntervals, timeIntervalsLoading]);

  useEffect(() => {
    if (!recipientCounterparties.length || activeRecipientCounterpartyIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(recipientCounterpartyDropdownRef.current, "waybill-recipient-counterparty", activeRecipientCounterpartyIndex);
  }, [activeRecipientCounterpartyIndex, recipientCounterparties.length]);

  useEffect(() => {
    if (!settlements.length || activeSettlementIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(cityDropdownRef.current, "waybill-city", activeSettlementIndex);
  }, [activeSettlementIndex, settlements.length]);

  useEffect(() => {
    if (!streets.length || activeStreetIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(streetDropdownRef.current, "waybill-street", activeStreetIndex);
  }, [activeStreetIndex, streets.length]);

  useEffect(() => {
    if (!warehouses.length || activeWarehouseIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(warehouseDropdownRef.current, "waybill-warehouse", activeWarehouseIndex);
  }, [activeWarehouseIndex, warehouses.length]);

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
  }, [isOpen, seatOptions, selectedSeatIndex]);

  useEffect(() => {
    if (!isOpen || !isSeatListMode) {
      return;
    }
    const target = seatListButtonsRef.current[selectedSeatIndex] || seatListButtonsRef.current[0];
    target?.focus();
  }, [isOpen, isSeatListMode, seatOptions.length, selectedSeatIndex]);

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
  const hasSelectedPackings = selectedPackRefs.length > 0;
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

  if (!isOpen) {
    return null;
  }

  const isBusy = isLoading || isSubmitting || isSyncing || isDeleting;
  const isReadonlyDocument = Boolean(waybill && !waybill.can_edit);
  const formDisabled = isBusy || isReadonlyDocument;
  const senderCounterpartyDisplay = getSenderMetaLabel(sender, "counterparty_label");
  const senderCityDisplay = getSenderMetaLabel(sender, "city_label");
  const senderAddressDisplay = getSenderMetaLabel(sender, "address_label");
  const senderPreview = resolveSenderPreview();
  const activeSeat = seatOptions[selectedSeatIndex] || seatOptions[0] || resolveSeatOptionFromPayload(payload);
  const payerTypeUi = (payload.payer_type || waybill?.payer_type || senderPreview.payer || "Recipient") as "Sender" | "Recipient" | "ThirdPerson";
  const paymentMethodUi = (payload.payment_method || waybill?.payment_method || senderPreview.payment || "Cash") as "Cash" | "NonCash";
  const cargoTypeUi = (activeSeat.cargo_type || payload.cargo_type || waybill?.cargo_type || "Parcel") as "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels";
  const usesControlPayment = senderRequiresControlPayment;
  const paymentAmountFieldLabel = usesControlPayment
    ? t("orders.modals.waybill.additional.controlPaymentAmount")
    : t("orders.modals.waybill.additional.cashOnDeliveryAmount");
  let paymentValidationMessage = "";
  if (payerTypeUi === "ThirdPerson" && !thirdPersonSupported) {
    paymentValidationMessage = t("orders.modals.waybill.meta.validation.thirdPersonUnavailable");
  } else if (paymentMethodUi === "NonCash" && !nonCashSupported) {
    paymentValidationMessage = t("orders.modals.waybill.meta.validation.nonCashUnavailable");
  } else if (payerTypeUi === "Recipient" && recipientIsPrivatePerson && paymentMethodUi === "NonCash") {
    paymentValidationMessage = t("orders.modals.waybill.meta.validation.nonCashUnavailableForPrivateRecipient");
  } else if (payerTypeUi === "ThirdPerson" && paymentMethodUi !== "NonCash") {
    paymentValidationMessage = t("orders.modals.waybill.meta.validation.thirdPersonRequiresNonCash");
  }
  const canSubmit = canSaveWaybill(payload) && !formDisabled && !paymentValidationMessage && !preferredDeliveryDateInvalid;
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
  const recipientCounterpartyDropdownStyle = (recipientCounterpartyLoading || recipientCounterparties.length > 0)
    ? computeFloatingDropdownStyle(recipientCounterpartyInputRef.current)
    : null;
  const cityDropdownStyle = (settlementLoading || settlements.length > 0)
    ? computeFloatingDropdownStyle(cityInputRef.current)
    : null;
  const streetDropdownStyle = (streetLoading || streets.length > 0)
    ? computeFloatingDropdownStyle(streetInputRef.current)
    : null;
  const warehouseDropdownStyle = (warehouseLoading || warehouses.length > 0)
    ? computeFloatingDropdownStyle(warehouseInputRef.current)
    : null;
  const packingsDropdownStyle = (isPackagingMode && (packingsLoading || visiblePackings.length > 0))
    && packingsDropdownOpen
    ? computeFloatingDropdownStyle(packingsInputRef.current, { maxHeight: 420 })
    : null;
  const applyWarehouseSuggestionSelection = (item: WaybillAddressSuggestion) => {
    setWarehouses([]);
    setActiveWarehouseIndex(-1);
    if (item.kind === "street") {
      const { suffix } = splitAddressInput(warehouseQuery);
      const { house, apartment } = parseHouseApartmentFromSuffix(suffix);
      const nextQuery = suffix ? `${item.label}, ${suffix}` : item.label;
      skipNextStreetLookupRef.current = true;
      skipNextWarehouseLookupRef.current = true;
      setSelectedSettlementRef(item.settlementRef || selectedSettlementRef);
      setWarehouseQuery(nextQuery);
      setStreets([]);
      setActiveStreetIndex(-1);
      setPayload((prev) => ({
        ...prev,
        delivery_type: "address",
        recipient_address_ref: "",
        recipient_address_label: "",
        recipient_street_ref: item.ref,
        recipient_street_label: item.label,
        recipient_house: house,
        recipient_apartment: apartment,
      }));
      return;
    }
    skipNextWarehouseLookupRef.current = true;
    setWarehouseQuery(item.label);
    const normalizedSuggestionText = `${item.label} ${item.subtitle}`.toLowerCase();
    const isPostomatSuggestion =
      normalizedSuggestionText.includes("поштомат")
      || normalizedSuggestionText.includes("почтомат")
      || normalizedSuggestionText.includes("постомат")
      || normalizedSuggestionText.includes("postomat");
    setPayload((prev) => ({
      ...prev,
      delivery_type: isPostomatSuggestion ? "postomat" : "warehouse",
      recipient_address_ref: item.ref,
      recipient_address_label: item.label,
      recipient_street_ref: "",
      recipient_street_label: "",
      recipient_house: "",
      recipient_apartment: "",
    }));
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
  const payloadForSave: WaybillFormPayload = {
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
  const applySettlementSelection = (settlement: BackofficeNovaPoshtaLookupSettlement) => {
    skipNextSettlementLookupRef.current = true;
    setSelectedSettlementRef(settlement.settlement_ref || settlement.ref || "");
    setCityQuery(settlement.label);
    setSettlements([]);
    setActiveSettlementIndex(-1);
    setStreetQuery("");
    setStreets([]);
    setActiveStreetIndex(-1);
    setWarehouseQuery("");
    setWarehouses([]);
    setActiveWarehouseIndex(-1);
    setPayload((prev) => ({
      ...prev,
      recipient_city_ref: settlement.delivery_city_ref || settlement.ref,
      recipient_city_label: settlement.label,
      recipient_address_ref: "",
      recipient_address_label: "",
      recipient_street_ref: "",
      recipient_street_label: "",
      recipient_house: "",
      recipient_apartment: "",
    }));
  };
  const applyRecipientCounterpartySelection = (counterparty: BackofficeNovaPoshtaLookupCounterparty) => {
    const resolvedCounterpartyRef = (counterparty.counterparty_ref || counterparty.ref || "").trim();
    const fallbackContactRef = (counterparty.ref || "").trim();
    const normalizedName = (counterparty.label || counterparty.full_name || "").trim();
    const normalizedPhone = normalizeWaybillPhone(counterparty.phone || "");
    const normalizedCityRef = (counterparty.city_ref || "").trim();
    const normalizedCityLabel = (counterparty.city_label || "").trim();

    skipNextRecipientCounterpartyLookupRef.current = true;
    setRecipientCounterpartyQuery(normalizedName);
    setRecipientCounterpartyTypeLabel(resolveCounterpartyTypeDisplay(counterparty.counterparty_type));
    setRecipientCounterpartyTypeRaw(counterparty.counterparty_type || "");
    setRecipientCounterparties([]);
    setActiveRecipientCounterpartyIndex(-1);

    if (normalizedCityRef) {
      skipNextSettlementLookupRef.current = true;
      setSelectedSettlementRef("");
      if (normalizedCityLabel) {
        setCityQuery(normalizedCityLabel);
      }
      setStreetQuery("");
      setStreets([]);
      setActiveStreetIndex(-1);
      setWarehouseQuery("");
      setWarehouses([]);
      setActiveWarehouseIndex(-1);
    }

    setPayload((prev) => {
      const nextPayload = {
        ...prev,
        recipient_counterparty_ref: resolvedCounterpartyRef,
        recipient_contact_ref: fallbackContactRef,
        recipient_name: normalizedName || prev.recipient_name,
        recipient_phone: normalizedPhone || prev.recipient_phone,
      };
      if (!normalizedCityRef) {
        return nextPayload;
      }
      return {
        ...nextPayload,
        recipient_city_ref: normalizedCityRef,
        recipient_city_label: normalizedCityLabel || prev.recipient_city_label,
        recipient_address_ref: "",
        recipient_address_label: "",
        recipient_street_ref: "",
        recipient_street_label: "",
        recipient_house: "",
        recipient_apartment: "",
      };
    });

    if (!token || !payload.sender_profile_id || !resolvedCounterpartyRef) {
      return;
    }

    const requestId = recipientCounterpartyDetailsRequestRef.current + 1;
    recipientCounterpartyDetailsRequestRef.current = requestId;
    void (async () => {
      try {
        const detailsResponse = await lookupBackofficeNovaPoshtaCounterpartyDetails(token, {
          sender_profile_id: payload.sender_profile_id,
          counterparty_ref: resolvedCounterpartyRef,
          counterparty_property: "Recipient",
          locale,
        });
        if (recipientCounterpartyDetailsRequestRef.current !== requestId) {
          return;
        }
        const details = detailsResponse.result;
        const detailsCityRef = (details.city_ref || "").trim();
        const detailsCityLabel = (details.city_label || "").trim();
        const detailsContactRef = (details.contact_ref || "").trim();
        const detailsContactName = (details.contact_name || "").trim();
        const detailsPhone = normalizeWaybillPhone(details.phone || "");

        if (detailsCityRef) {
          skipNextSettlementLookupRef.current = true;
          setSelectedSettlementRef("");
          if (detailsCityLabel) {
            setCityQuery(detailsCityLabel);
          }
          setStreetQuery("");
          setStreets([]);
          setActiveStreetIndex(-1);
          setWarehouseQuery("");
          setWarehouses([]);
          setActiveWarehouseIndex(-1);
        }

        setPayload((prev) => {
          const nextPayload = {
            ...prev,
            recipient_counterparty_ref: resolvedCounterpartyRef || prev.recipient_counterparty_ref,
            recipient_contact_ref: detailsContactRef || prev.recipient_contact_ref,
            recipient_name: detailsContactName || prev.recipient_name,
            recipient_phone: detailsPhone || prev.recipient_phone,
          };
          if (!detailsCityRef) {
            return nextPayload;
          }
          return {
            ...nextPayload,
            recipient_city_ref: detailsCityRef,
            recipient_city_label: detailsCityLabel || prev.recipient_city_label,
            recipient_address_ref: "",
            recipient_address_label: "",
            recipient_street_ref: "",
            recipient_street_label: "",
            recipient_house: "",
            recipient_apartment: "",
          };
        });
      } catch {
        if (recipientCounterpartyDetailsRequestRef.current !== requestId) {
          return;
        }
      }
    })();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
      <button type="button" className="absolute inset-0 bg-black/40" aria-label={t("orders.actions.closeModal")} onClick={onClose} />

      <div
        className="relative z-10 flex max-h-[94vh] w-[96vw] max-w-[1600px] flex-col overflow-hidden rounded-md border"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <header className="border-b px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold">{t("orders.modals.waybill.title")}</h2>
              <BackofficeStatusChip
                tone={waybill?.np_number ? "success" : "orange"}
                icon={waybill?.np_number ? ScanBarcode : ScanLine}
                className="h-7 px-2 py-0 tracking-wide"
              >
                {waybill?.np_number || t("orders.table.waybillEmpty")}
              </BackofficeStatusChip>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                aria-label={t("orders.actions.closeModal")}
                onClick={onClose}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </header>

        <div ref={contentScrollRef} className="flex-1 min-h-0 overflow-y-auto p-4">
          <div className="grid items-stretch gap-3 xl:grid-cols-4">
            <section
              className="order-1 rounded-md border p-3 xl:h-[460px] xl:overflow-y-auto"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <div className="flex min-h-8 items-center justify-between gap-2">
                <h3 className="text-foreground text-sm font-semibold">{t("orders.modals.waybill.fields.sender")}</h3>
                <div ref={senderMenuRef} className="relative">
                  <button
                    type="button"
                    className="inline-flex h-8 cursor-pointer items-center justify-center rounded-md border px-3"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
                    onClick={() => setSenderMenuOpen((prev) => !prev)}
                    disabled={formDisabled || senderProfiles.length === 0}
                    aria-label={t("orders.modals.waybill.fields.sender")}
                  >
                    <MoreHorizontal className="size-4 stroke-[2.5]" />
                  </button>
                  {senderMenuOpen ? (
                    <div
                      className="absolute right-0 top-[calc(100%+0.35rem)] z-[100] min-w-64 rounded-md border p-1.5 shadow-lg"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
                    >
                      <p className="px-2 py-1 text-xs" style={{ color: "var(--muted)" }}>
                        {t("orders.modals.waybill.fields.sender")}
                      </p>
                      <div className="px-2 pb-1 text-sm font-medium">{resolveSenderDisplayName(sender)}</div>
                      <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
                      {senderProfiles.length === 0 ? (
                        <p className="px-2 py-1 text-xs" style={{ color: "var(--muted)" }}>
                          {t("orders.modals.waybill.settings.empty")}
                        </p>
                      ) : (
                        <div className="grid gap-0.5">
                          {senderProfiles.map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100/70 dark:hover:bg-slate-700/40"
                              onClick={() => {
                                setPayload((prev) => ({ ...prev, sender_profile_id: item.id }));
                                setSenderMenuOpen(false);
                              }}
                            >
                              <span className="block">{resolveSenderDisplayName(item)}</span>
                              {item.is_default ? (
                                <span className="block text-xs" style={{ color: "var(--muted)" }}>
                                  {t("orders.modals.waybill.settings.default")}
                                </span>
                              ) : null}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="grid gap-1 pt-0.5">
                <div className="grid gap-1">
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.settings.form.phone")}</span>
                  <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <span className={sender?.phone ? "text-[var(--text)]" : "text-[var(--muted)]"}>{sender?.phone || "—"}</span>
                  </div>
                </div>

                <div className="grid gap-1">
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.counterparty")}</span>
                  <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <span className={senderCounterpartyDisplay ? "truncate text-[var(--text)]" : "truncate text-[var(--muted)]"}>
                      {senderCounterpartyDisplay || "—"}
                    </span>
                  </div>
                </div>

                <div className="grid gap-1">
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.settings.form.contactName")}</span>
                  <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <span className={sender?.contact_name ? "text-[var(--text)]" : "text-[var(--muted)]"}>{sender?.contact_name || "—"}</span>
                  </div>
                </div>

                <div className="grid gap-1">
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.settings.form.cityRef")}</span>
                  <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <span className={senderCityDisplay ? "truncate text-[var(--text)]" : "truncate text-[var(--muted)]"}>
                      {senderCityDisplay || "—"}
                    </span>
                  </div>
                </div>

                <div className="grid gap-1">
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.settings.form.addressRef")}</span>
                  <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <span className={senderAddressDisplay ? "truncate text-[var(--text)]" : "truncate text-[var(--muted)]"}>
                      {senderAddressDisplay || "—"}
                    </span>
                  </div>
                </div>
              </div>
            </section>

            {!isAdditionalServicesMode ? (
            <section
              className="order-3 rounded-md border p-3 xl:h-[460px]"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <div className="flex min-h-8 items-center gap-2">
                <h3 className="text-sm font-semibold">{t("orders.modals.waybill.sectionRecipient")}</h3>
              </div>

              <div className="grid gap-1 pt-0.5">
                <label className="grid gap-1 text-xs">
                  <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.recipientPhone")}</span>
                  <input
                    className="h-10 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    value={payload.recipient_phone}
                    disabled={formDisabled}
                    onChange={(event) => setPayload((prev) => ({ ...prev, recipient_phone: normalizeWaybillPhone(event.target.value) }))}
                  />
                </label>

                <label ref={recipientCounterpartyLookupRootRef} className="grid gap-1 text-xs">
                  <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.counterparty")}</span>
                  <input
                    ref={recipientCounterpartyInputRef}
                    className="h-10 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    value={recipientCounterpartyQuery}
                    disabled={formDisabled}
                    onChange={(event) => {
                      const next = event.target.value;
                      setRecipientCounterpartyTypeLabel("");
                      setRecipientCounterpartyTypeRaw("");
                      setRecipientCounterpartyQuery(next);
                      setRecipientCounterparties([]);
                      setActiveRecipientCounterpartyIndex(-1);
                      setPayload((prev) => ({
                        ...prev,
                        recipient_counterparty_ref: "",
                        recipient_contact_ref: "",
                      }));
                    }}
                    onBlur={() => {
                      if (recipientCounterpartyQuery.trim()) {
                        return;
                      }
                      skipNextRecipientCounterpartyLookupRef.current = true;
                      setRecipientCounterpartyTypeLabel(privateCounterpartyLabel);
                      setRecipientCounterpartyTypeRaw("PrivatePerson");
                      setRecipientCounterpartyQuery(privateCounterpartyLabel);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") {
                        setRecipientCounterparties([]);
                        setActiveRecipientCounterpartyIndex(-1);
                        return;
                      }
                      if (!recipientCounterparties.length) {
                        return;
                      }
                      if (event.key === "ArrowDown") {
                        event.preventDefault();
                        setActiveRecipientCounterpartyIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, recipientCounterparties.length - 1)));
                        return;
                      }
                      if (event.key === "ArrowUp") {
                        event.preventDefault();
                        setActiveRecipientCounterpartyIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                        return;
                      }
                      if (event.key === "Enter") {
                        event.preventDefault();
                        const resolvedIndex = activeRecipientCounterpartyIndex >= 0 ? activeRecipientCounterpartyIndex : 0;
                        const selected = recipientCounterparties[resolvedIndex];
                        if (selected) {
                          applyRecipientCounterpartySelection(selected);
                        }
                      }
                    }}
                    placeholder={t("orders.modals.waybill.fields.counterparty")}
                  />
                  {recipientCounterpartyTypeLabel && !recipientIsPrivatePerson ? (
                    <span className="truncate text-[11px]" style={{ color: "var(--muted)" }}>
                      {recipientCounterpartyTypeLabel}
                    </span>
                  ) : null}
                  {recipientCounterpartyLoading || !recipientIsPrivatePerson ? (
                    <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                      {recipientCounterpartyLoading
                        ? t("orders.modals.waybill.fields.counterpartyLookupLoading")
                        : t("orders.modals.waybill.fields.counterpartyBusinessCodeHint")}
                    </p>
                  ) : null}
                </label>

                <label className="grid gap-1 text-xs">
                  <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.recipientName")}</span>
                  <input
                    className="h-10 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    value={payload.recipient_name}
                    disabled={formDisabled}
                    onChange={(event) => setPayload((prev) => ({ ...prev, recipient_name: event.target.value }))}
                  />
                </label>

                <label ref={cityLookupRootRef} className="relative grid gap-1 text-xs">
                  <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.city")}</span>
                  <input
                    ref={cityInputRef}
                    className="h-10 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    value={cityQuery}
                    disabled={formDisabled}
                    onChange={(event) => {
                      const next = event.target.value;
                      setSelectedSettlementRef("");
                      setCityQuery(next);
                      setSettlements([]);
                      setActiveSettlementIndex(-1);
                      setStreets([]);
                      setActiveStreetIndex(-1);
                      setWarehouses([]);
                      setActiveWarehouseIndex(-1);
                      setPayload((prev) => ({
                        ...prev,
                        recipient_city_ref: "",
                        recipient_city_label: next,
                        recipient_address_ref: "",
                        recipient_address_label: "",
                        recipient_street_ref: "",
                        recipient_street_label: "",
                        recipient_house: "",
                        recipient_apartment: "",
                      }));
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") {
                        setSettlements([]);
                        setActiveSettlementIndex(-1);
                        return;
                      }
                      if (!settlements.length) {
                        return;
                      }
                      if (event.key === "ArrowDown") {
                        event.preventDefault();
                        setActiveSettlementIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, settlements.length - 1)));
                        return;
                      }
                      if (event.key === "ArrowUp") {
                        event.preventDefault();
                        setActiveSettlementIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                        return;
                      }
                      if (event.key === "Enter") {
                        event.preventDefault();
                        const resolvedIndex = activeSettlementIndex >= 0 ? activeSettlementIndex : 0;
                        const selected = settlements[resolvedIndex];
                        if (!selected) {
                          return;
                        }
                        applySettlementSelection(selected);
                      }
                    }}
                    placeholder={t("orders.modals.waybill.fields.cityPlaceholder")}
                  />
                  {null}
                </label>

                <label ref={warehouseLookupRootRef} className="relative grid gap-1 text-xs">
                  <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.warehouse")}</span>
                  <input
                    ref={warehouseInputRef}
                    className="h-10 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    value={warehouseQuery}
                    disabled={formDisabled || !payload.recipient_city_ref}
                    onChange={(event) => {
                      const next = event.target.value;
                      const { base, suffix } = splitAddressInput(next);
                      const { house, apartment } = parseHouseApartmentFromSuffix(suffix);
                      const normalizedBase = base.trim().toLowerCase();
                      setWarehouseQuery(next);
                      setWarehouses([]);
                      setActiveWarehouseIndex(-1);
                      setStreets([]);
                      setActiveStreetIndex(-1);
                      setPayload((prev) => {
                        const selectedStreetLabel = (prev.recipient_street_label || "").trim().toLowerCase();
                        const keepStreetRef = Boolean(prev.recipient_street_ref && selectedStreetLabel && normalizedBase === selectedStreetLabel);
                        const hasLettersInBase = /[A-Za-zА-Яа-яІіЇїЄєҐґ]/.test(base);
                        if (keepStreetRef || hasLettersInBase) {
                          return {
                            ...prev,
                            delivery_type: "address",
                            recipient_address_ref: "",
                            recipient_address_label: "",
                            recipient_street_ref: keepStreetRef ? prev.recipient_street_ref : "",
                            recipient_street_label: keepStreetRef ? prev.recipient_street_label : base,
                            recipient_house: house,
                            recipient_apartment: apartment,
                          };
                        }
                        return {
                          ...prev,
                          delivery_type: prev.delivery_type === "postomat" ? "postomat" : "warehouse",
                          recipient_address_ref: "",
                          recipient_address_label: next,
                          recipient_street_ref: "",
                          recipient_street_label: "",
                          recipient_house: "",
                          recipient_apartment: "",
                        };
                      });
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") {
                        setWarehouses([]);
                        setActiveWarehouseIndex(-1);
                        return;
                      }
                      if (!warehouses.length) {
                        return;
                      }
                      if (event.key === "ArrowDown") {
                        event.preventDefault();
                        setActiveWarehouseIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, warehouses.length - 1)));
                        return;
                      }
                      if (event.key === "ArrowUp") {
                        event.preventDefault();
                        setActiveWarehouseIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                        return;
                      }
                      if (event.key === "Enter") {
                        event.preventDefault();
                        const resolvedIndex = activeWarehouseIndex >= 0 ? activeWarehouseIndex : 0;
                        const selected = warehouses[resolvedIndex];
                        if (!selected) {
                          return;
                        }
                        applyWarehouseSuggestionSelection(selected);
                      }
                    }}
                    placeholder="Отделение / почтомат / адрес"
                  />
                  {null}
                  <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
                    {!payload.recipient_city_ref
                      ? "Сначала выберите город."
                      : warehouseLoading
                        ? "Ищем отделения/почтоматы..."
                        : "Цифры: от 1 символа, текст: от 2 символов. Для адреса: улица, дом/кв."}
                  </p>
                </label>
              </div>
            </section>
            ) : null}

            <section
              className="order-2 rounded-md border p-3 xl:h-[460px] xl:overflow-y-auto"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <div className="flex h-8 items-center justify-between gap-2">
                <div className="flex min-w-0 items-baseline gap-2">
                  <h3 className="text-foreground whitespace-nowrap text-sm font-semibold">{t("orders.modals.waybill.sectionShipment")}</h3>
                  <span className="truncate whitespace-nowrap text-xs" style={{ color: "var(--muted)" }}>
                    {t("orders.modals.waybill.fields.seats")}: {selectedSeatIndex + 1}/{normalizedSeatsAmount}
                  </span>
                </div>
                {isPackagingMode || isSeatListMode ? (
                  <button
                    type="button"
                    className="inline-flex h-8 items-center justify-center gap-1 rounded-md border px-2.5 text-xs font-semibold"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
                    onClick={() => {
                      setIsSeatListMode(false);
                      leavePackagingMode();
                    }}
                    disabled={formDisabled}
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    <span>{isSeatListMode ? t("orders.modals.waybill.actions.backFromSeatList") : t("orders.modals.waybill.actions.backFromPackaging")}</span>
                  </button>
                ) : (
                  <div ref={seatMenuRef} className="relative">
                    <button
                      type="button"
                      className="inline-flex h-8 cursor-pointer items-center justify-center rounded-md border px-3"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
                      aria-label={t("orders.modals.waybill.fields.seats")}
                      onClick={() => setSeatMenuOpen((prev) => !prev)}
                      disabled={formDisabled}
                    >
                      <MoreHorizontal className="size-4 stroke-[2.5]" />
                    </button>
                  {seatMenuOpen ? (
                    <div
                      className="absolute right-0 top-[calc(100%+0.35rem)] z-[100] min-w-56 rounded-md border p-1.5 shadow-lg"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
                    >
                        <button
                          type="button"
                          className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100/70 dark:hover:bg-slate-700/40"
                          onClick={addSeat}
                        >
                          {t("orders.modals.waybill.actions.addSeat")}
                        </button>
                        {normalizedSeatsAmount > 1 ? (
                          <button
                            type="button"
                            className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100/70 dark:hover:bg-slate-700/40"
                            onClick={removeSeat}
                          >
                            {t("orders.modals.waybill.actions.removeSeat")}
                          </button>
                        ) : null}
                        {normalizedSeatsAmount > 1 ? (
                          <>
                            <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
                            <button
                              type="button"
                              className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100/70 dark:hover:bg-slate-700/40"
                              onClick={enterSeatListMode}
                            >
                              {t("orders.modals.waybill.actions.seatList")}
                            </button>
                          </>
                        ) : null}
                        <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
                        <p className="px-2 py-1 text-xs" style={{ color: "var(--muted)" }}>
                          {t("orders.modals.waybill.fields.seats")}: {normalizedSeatsAmount}
                        </p>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
              {isSeatListMode ? (
                <div className="grid gap-2 pt-0.5">
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {t("orders.modals.waybill.actions.seatList")}
                  </p>
                  <div
                    className="grid gap-2"
                    role="listbox"
                    aria-label={t("orders.modals.waybill.actions.seatList")}
                    onKeyDown={(event) => {
                      if (!seatOptions.length) {
                        return;
                      }
                      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
                        return;
                      }
                      event.preventDefault();
                      const direction = event.key === "ArrowDown" ? 1 : -1;
                      const current = selectedSeatIndex;
                      const next = Math.max(0, Math.min(current + direction, seatOptions.length - 1));
                      setSelectedSeatIndex(next);
                      seatListButtonsRef.current[next]?.focus();
                    }}
                  >
                    {seatOptions.map((seat, index) => (
                      <button
                        key={`seat-list-${index}`}
                        ref={(node) => {
                          seatListButtonsRef.current[index] = node;
                        }}
                        type="button"
                        className="rounded-md border px-3 py-2 text-left text-sm"
                        style={{
                          borderColor: selectedSeatIndex === index ? "#2563eb" : "var(--border)",
                          backgroundColor: selectedSeatIndex === index ? "rgba(37,99,235,0.08)" : "var(--surface-2)",
                        }}
                        role="option"
                        aria-selected={selectedSeatIndex === index}
                        onClick={() => openSeatForEditing(index)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            openSeatForEditing(index);
                          }
                        }}
                      >
                        <p className="font-semibold">
                          {t("orders.modals.waybill.actions.seatCardTitle", { index: index + 1 })}
                        </p>
                        <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
                          {t("orders.modals.waybill.fields.weight")}: {seat.weight || "-"}
                        </p>
                        <p className="text-xs" style={{ color: "var(--muted)" }}>
                          {t("orders.modals.waybill.fields.cost")}: {seat.cost || "-"}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              ) : isPackagingMode ? (
                <div className="grid gap-1 pt-0.5">
                  <label ref={packingsLookupRootRef} className="grid min-w-0 gap-1 text-xs">
                    <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.packRef")}</span>
                    <input
                      ref={packingsInputRef}
                      className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      value={selectedPackingsDisplay}
                      placeholder={t("orders.modals.waybill.fields.packRefHint")}
                      disabled={formDisabled}
                      readOnly
                      onFocus={() => setPackingsDropdownOpen(true)}
                      onClick={() => setPackingsDropdownOpen(true)}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") {
                          setPackingsDropdownOpen(false);
                        }
                      }}
                    />
                    <span className="text-[11px]" style={{ color: "var(--muted)" }}>
                      {t("orders.modals.waybill.fields.packRefHint")}
                    </span>
                    {packingsLoading ? (
                      <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                        {t("orders.modals.waybill.fields.packRefLoading")}
                      </p>
                    ) : null}
                    {!packingsLoading && !visiblePackings.length ? (
                      <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                        {t("orders.modals.waybill.fields.packRefEmpty")}
                      </p>
                    ) : null}
                  </label>
                </div>
              ) : (
                <div className="grid gap-1 pt-0.5">
                  <label className="grid gap-1 text-xs">
                    <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.description")}</span>
                    <input
                      className="h-10 rounded-md border px-3 text-sm"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      value={activeSeat.description || ""}
                      disabled={formDisabled}
                      onChange={(event) => updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                        index === activeIndex
                          ? { ...seat, description: event.target.value }
                          : seat
                      )))}
                    />
                  </label>

                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 sm:items-end">
                    <label className="grid min-w-0 gap-1 text-xs">
                      <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.cost")}</span>
                      <input
                        className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        value={activeSeat.cost || ""}
                        disabled={formDisabled}
                        onChange={(event) => updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                          index === activeIndex
                            ? { ...seat, cost: event.target.value }
                            : seat
                        )))}
                      />
                    </label>
                    <label className="grid min-w-0 gap-1 text-xs">
                      <span className="truncate" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.weight")}</span>
                      <input
                        className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        value={activeSeat.weight || ""}
                        disabled={formDisabled}
                        onChange={(event) => updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                          index === activeIndex
                            ? { ...seat, weight: event.target.value }
                            : seat
                        )))}
                      />
                    </label>
                  </div>

                  <div className="grid gap-1">
                    <span aria-hidden="true" className="text-xs opacity-0">.</span>
                    <button
                      type="button"
                      className="h-10 rounded-md border px-3 text-sm font-semibold"
                      style={{
                        borderColor: hasSelectedPackings ? "#3f8a5a" : "#2563eb",
                        backgroundColor: hasSelectedPackings ? "#4b9264" : "#2563eb",
                        color: hasSelectedPackings ? "#f7fffa" : "#fff",
                      }}
                      disabled={formDisabled}
                      onClick={enterPackagingMode}
                    >
                      {hasSelectedPackings
                        ? t("orders.modals.waybill.actions.packagingAdded")
                        : t("orders.modals.waybill.actions.addPackaging")}
                    </button>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
                    <label className="grid min-w-0 gap-1 text-xs">
                      <span className="truncate" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.widthCm")}</span>
                      <input
                        className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        value={packagingWidth}
                        disabled={formDisabled}
                        onChange={(event) => {
                          const nextValue = event.target.value;
                          setPackagingWidth(nextValue);
                          setIsPackagingEnabled(true);
                          updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                            index === activeIndex
                              ? { ...seat, volumetric_width: nextValue }
                              : seat
                          )));
                        }}
                      />
                    </label>
                    <label className="grid min-w-0 gap-1 text-xs">
                      <span className="truncate" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.lengthCm")}</span>
                      <input
                        className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        value={packagingLength}
                        disabled={formDisabled}
                        onChange={(event) => {
                          const nextValue = event.target.value;
                          setPackagingLength(nextValue);
                          setIsPackagingEnabled(true);
                          updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                            index === activeIndex
                              ? { ...seat, volumetric_length: nextValue }
                              : seat
                          )));
                        }}
                      />
                    </label>
                    <label className="grid min-w-0 gap-1 text-xs">
                      <span className="truncate" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.heightCm")}</span>
                      <input
                        className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        value={packagingHeight}
                        disabled={formDisabled}
                        onChange={(event) => {
                          const nextValue = event.target.value;
                          setPackagingHeight(nextValue);
                          setIsPackagingEnabled(true);
                          updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                            index === activeIndex
                              ? { ...seat, volumetric_height: nextValue }
                              : seat
                          )));
                        }}
                      />
                    </label>
                  </div>

                  <div className="grid gap-1">
                    <span aria-hidden="true" className="text-xs opacity-0">.</span>
                    <div
                      className="rounded-md flex h-10 min-w-0 items-center justify-center gap-2 border px-3 text-sm text-center"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    >
                      <span className="font-semibold text-[var(--text)]">
                        {t("orders.modals.waybill.fields.volumetricWeight")}
                      </span>
                      <span style={{ color: "var(--muted)" }}>
                        {volumetricWeight} {t("orders.modals.waybill.fields.weightUnit")}
                      </span>
                    </div>
                  </div>

                  <div className="grid gap-1">
                    <span aria-hidden="true" className="text-xs opacity-0">.</span>
                    <div className="flex items-center justify-center gap-2">
                      <BackofficeTooltip content={t("orders.modals.waybill.cargoTypes.documents")} placement="bottom" align="center" wrapperClassName="inline-flex">
                        <button
                          type="button"
                          className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
                          style={{
                            borderColor: cargoTypeUi === "Documents" ? "#2563eb" : "var(--border)",
                            backgroundColor: cargoTypeUi === "Documents" ? "#2563eb" : "var(--surface-2)",
                            color: cargoTypeUi === "Documents" ? "#fff" : "var(--muted)",
                          }}
                          disabled={formDisabled}
                          onClick={() => applyCargoTypeSelection("Documents")}
                        >
                          <FileText className="h-4 w-4" />
                        </button>
                      </BackofficeTooltip>
                      <BackofficeTooltip content={t("orders.modals.waybill.cargoTypes.parcel")} placement="bottom" align="center" wrapperClassName="inline-flex">
                        <button
                          type="button"
                          className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
                          style={{
                            borderColor: cargoTypeUi === "Parcel" ? "#2563eb" : "var(--border)",
                            backgroundColor: cargoTypeUi === "Parcel" ? "#2563eb" : "var(--surface-2)",
                            color: cargoTypeUi === "Parcel" ? "#fff" : "var(--muted)",
                          }}
                          disabled={formDisabled}
                          onClick={() => applyCargoTypeSelection("Parcel")}
                        >
                          <Archive className="h-4 w-4" />
                        </button>
                      </BackofficeTooltip>
                      <BackofficeTooltip content={t("orders.modals.waybill.cargoTypes.cargo")} placement="bottom" align="center" wrapperClassName="inline-flex">
                        <button
                          type="button"
                          className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
                          style={{
                            borderColor: cargoTypeUi === "Cargo" ? "#2563eb" : "var(--border)",
                            backgroundColor: cargoTypeUi === "Cargo" ? "#2563eb" : "var(--surface-2)",
                            color: cargoTypeUi === "Cargo" ? "#fff" : "var(--muted)",
                          }}
                          disabled={formDisabled}
                          onClick={() => applyCargoTypeSelection("Cargo")}
                        >
                          <Truck className="h-4 w-4" />
                        </button>
                      </BackofficeTooltip>
                      <BackofficeTooltip content={t("orders.modals.waybill.cargoTypes.pallet")} placement="bottom" align="center" wrapperClassName="inline-flex">
                        <button
                          type="button"
                          className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
                          style={{
                            borderColor: cargoTypeUi === "Pallet" ? "#2563eb" : "var(--border)",
                            backgroundColor: cargoTypeUi === "Pallet" ? "#2563eb" : "var(--surface-2)",
                            color: cargoTypeUi === "Pallet" ? "#fff" : "var(--muted)",
                          }}
                          disabled={formDisabled}
                          onClick={() => applyCargoTypeSelection("Pallet")}
                        >
                          <Circle className="h-4 w-4" />
                        </button>
                      </BackofficeTooltip>
                    </div>
                  </div>
                </div>
              )}
            </section>

            <section
              className={`${isAdditionalServicesMode ? "order-3 xl:col-span-2" : "order-4"} rounded-md border p-3 xl:h-[460px] xl:overflow-y-auto`}
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <div className="flex h-8 items-center justify-between gap-2">
                <h3 className="text-foreground whitespace-nowrap text-sm font-semibold">
                  {isAdditionalServicesMode
                    ? t("orders.modals.waybill.actions.additionalServices")
                    : t("orders.modals.waybill.sectionPaymentAdditional")}
                </h3>
                {isAdditionalServicesMode ? (
                  <button
                    type="button"
                    className="inline-flex h-8 cursor-pointer items-center justify-center gap-1 rounded-md border px-3 text-xs font-semibold"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
                    onClick={leaveAdditionalServicesMode}
                    disabled={formDisabled}
                  >
                    <ArrowLeft className="size-4 stroke-[2.5]" />
                    <span>{t("orders.modals.waybill.actions.backFromAdditionalServices")}</span>
                  </button>
                ) : null}
              </div>

              <div className="grid gap-1 pt-0.5">
                {!isAdditionalServicesMode ? (
                  <>
                <div className="grid gap-1 pb-1">
                  <span className="text-xs opacity-0" style={{ color: "var(--muted)" }} aria-hidden>
                    {t("orders.modals.waybill.fields.cost")}
                  </span>
                  <div className="grid min-h-[96px] min-w-0 content-start gap-1 rounded-md border px-3 py-1.5 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <div className="flex min-w-0 items-center justify-between gap-2">
                      <span className="min-w-0 font-medium" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.payment.toPay")}</span>
                      <span className="shrink-0 font-semibold">—</span>
                    </div>
                    <div className="flex min-w-0 items-center justify-between gap-2">
                      <span className="min-w-0 font-medium" style={{ color: "var(--muted)" }}>{paymentAmountFieldLabel}</span>
                      <span className="shrink-0 font-semibold">{payload.afterpayment_amount || "0"} {order?.currency || ""}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-1 grid gap-1">
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.meta.payerType")}</span>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {(["Sender", "Recipient", "ThirdPerson"] as const).map((value) => (
                      <button
                        key={value}
                        type="button"
                        className="h-10 rounded-md border px-4 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                        style={{
                          borderColor: payerTypeUi === value ? "#2563eb" : "var(--border)",
                          backgroundColor: payerTypeUi === value ? "#2563eb" : "var(--surface)",
                          color: payerTypeUi === value ? "#fff" : "var(--text)",
                        }}
                        disabled={formDisabled || (value === "ThirdPerson" && !thirdPersonSupported)}
                        onClick={() => applyPayerTypeSelection(value)}
                      >
                        {resolvePayerTypeLabel(value, t)}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid gap-1">
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.meta.paymentMethod")}</span>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {(["Cash", "NonCash"] as const).map((value) => (
                      <button
                        key={value}
                        type="button"
                        className="h-10 rounded-md border px-4 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                        style={{
                          borderColor: paymentMethodUi === value ? "#2563eb" : "var(--border)",
                          backgroundColor: paymentMethodUi === value ? "#2563eb" : "var(--surface)",
                          color: paymentMethodUi === value ? "#fff" : "var(--text)",
                        }}
                        disabled={
                          formDisabled
                          || (payerTypeUi === "ThirdPerson" && value === "Cash")
                          || (payerTypeUi === "Recipient" && recipientIsPrivatePerson && value === "NonCash")
                          || (value === "NonCash" && !nonCashSupported)
                        }
                        onClick={() => applyPaymentMethodSelection(value)}
                      >
                        {resolvePaymentMethodLabel(value, t)}
                      </button>
                    ))}
                  </div>
                </div>
                {paymentValidationMessage ? (
                  <div
                    className="rounded-md border px-2 py-1.5 text-xs"
                    style={{ borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,.12)", color: "#92400e" }}
                  >
                    {paymentValidationMessage}
                  </div>
                ) : null}
                  </>
                ) : null}

                {isAdditionalServicesMode ? (
                  <div className="grid gap-1 md:grid-cols-2 xl:grid-cols-3">
                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{paymentAmountFieldLabel}</span>
                        <input
                          className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          value={payload.afterpayment_amount || ""}
                          disabled={formDisabled}
                          onChange={(event) => setPayload((prev) => ({ ...prev, afterpayment_amount: event.target.value }))}
                        />
                      </label>
                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.infoRegClientBarcodes")}</span>
                        <input
                          className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          value={payload.info_reg_client_barcodes || ""}
                          disabled={formDisabled}
                          onChange={(event) => setPayload((prev) => ({ ...prev, info_reg_client_barcodes: event.target.value }))}
                        />
                      </label>

                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.saturdayDelivery")}</span>
                        <div
                          className="flex h-10 w-full min-w-0 items-center rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        >
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={Boolean(payload.saturday_delivery)}
                              disabled={formDisabled}
                              onChange={(event) => setPayload((prev) => ({ ...prev, saturday_delivery: event.target.checked }))}
                            />
                            <span className="font-semibold">{t("orders.modals.waybill.additional.saturdayDelivery")}</span>
                          </label>
                        </div>
                      </label>

                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.localExpress")}</span>
                        <div
                          className="flex h-10 w-full min-w-0 items-center rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        >
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={Boolean(payload.local_express)}
                              disabled={formDisabled}
                              onChange={(event) => setPayload((prev) => ({ ...prev, local_express: event.target.checked }))}
                            />
                            <span className="font-semibold">{t("orders.modals.waybill.additional.localExpress")}</span>
                          </label>
                        </div>
                      </label>

                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.deliveryByHand")}</span>
                        <div
                          className="flex h-10 w-full min-w-0 items-center rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        >
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={Boolean(payload.delivery_by_hand)}
                              disabled={formDisabled}
                              onChange={(event) => setPayload((prev) => ({ ...prev, delivery_by_hand: event.target.checked }))}
                            />
                            <span className="font-semibold">{t("orders.modals.waybill.additional.deliveryByHand")}</span>
                          </label>
                        </div>
                      </label>

                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.specialCargo")}</span>
                        <div
                          className="flex h-10 w-full min-w-0 items-center rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        >
                          <label className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={Boolean(payload.special_cargo)}
                              disabled={formDisabled}
                              onChange={(event) => setPayload((prev) => ({ ...prev, special_cargo: event.target.checked }))}
                            />
                            <span className="font-semibold">{t("orders.modals.waybill.additional.specialCargo")}</span>
                          </label>
                        </div>
                      </label>
                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.preferredDeliveryDate")}</span>
                        <input
                          className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                          style={{
                            borderColor: preferredDeliveryDateInvalid ? "#ef4444" : "var(--border)",
                            backgroundColor: "var(--surface-2)",
                          }}
                          value={payload.preferred_delivery_date || ""}
                          disabled={formDisabled || deliveryDateLookupLoading}
                          placeholder={deliveryDateLookup?.date || t("orders.modals.waybill.additional.datePlaceholder")}
                          inputMode="numeric"
                          maxLength={10}
                          onChange={(event) => setPayload((prev) => ({
                            ...prev,
                            preferred_delivery_date: formatPreferredDeliveryDateInput(event.target.value),
                          }))}
                          onBlur={() => setPayload((prev) => ({
                            ...prev,
                            preferred_delivery_date: normalizePreferredDeliveryDate(prev.preferred_delivery_date || ""),
                          }))}
                        />
                      </label>
                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.timeInterval")}</span>
                        <select
                          className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          value={payload.time_interval || ""}
                          disabled={formDisabled || !payload.recipient_city_ref || timeIntervalsLoading}
                          onChange={(event) => {
                            const value = event.target.value as WaybillFormPayload["time_interval"];
                            setPayload((prev) => ({ ...prev, time_interval: value }));
                          }}
                        >
                          <option value="">{t("orders.modals.waybill.additional.timeIntervalNone")}</option>
                          {timeIntervalOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.accompanyingDocuments")}</span>
                        <input
                          className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          value={payload.accompanying_documents || ""}
                          disabled={formDisabled}
                          onChange={(event) => setPayload((prev) => ({ ...prev, accompanying_documents: event.target.value }))}
                        />
                      </label>
                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.redBoxBarcode")}</span>
                        <input
                          className="h-10 w-full min-w-0 rounded-md border px-3 text-sm uppercase"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          value={payload.red_box_barcode || ""}
                          disabled={formDisabled}
                          onChange={(event) => setPayload((prev) => ({ ...prev, red_box_barcode: event.target.value.toUpperCase() }))}
                        />
                      </label>
                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.forwardingCount")}</span>
                        <input
                          className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          value={payload.forwarding_count || ""}
                          disabled={formDisabled}
                          onChange={(event) => setPayload((prev) => ({ ...prev, forwarding_count: event.target.value }))}
                        />
                      </label>
                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.numberOfFloorsLifting")}</span>
                        <input
                          className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          value={payload.number_of_floors_lifting || ""}
                          disabled={formDisabled}
                          onChange={(event) => setPayload((prev) => ({ ...prev, number_of_floors_lifting: event.target.value }))}
                        />
                      </label>
                      <label className="grid min-w-0 gap-1 text-xs">
                        <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.numberOfFloorsDescent")}</span>
                        <input
                          className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          value={payload.number_of_floors_descent || ""}
                          disabled={formDisabled}
                          onChange={(event) => setPayload((prev) => ({ ...prev, number_of_floors_descent: event.target.value }))}
                        />
                      </label>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="mt-5 h-10 rounded-md border px-3 text-sm font-medium"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
                    disabled={formDisabled}
                    onClick={enterAdditionalServicesMode}
                  >
                    {t("orders.modals.waybill.actions.additionalServices")}
                  </button>
                )}

                {waybill?.last_sync_error ? (
                  <div
                    className="rounded-md border px-2 py-1.5 text-xs"
                    style={{ borderColor: "#ef4444", backgroundColor: "rgba(239,68,68,.12)", color: "#991b1b" }}
                  >
                    <div className="flex items-start gap-1.5">
                      <AlertCircle className="mt-0.5 h-3.5 w-3.5" />
                      <span className="leading-4">{waybill.last_sync_error}</span>
                    </div>
                  </div>
                ) : null}
              </div>
            </section>
          </div>
        </div>

        {typeof document !== "undefined" && cityDropdownStyle ? createPortal(
          <div
            ref={cityDropdownRef}
            className="rounded-md border"
            style={{ ...cityDropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
            role="listbox"
            aria-label={t("orders.modals.waybill.fields.city")}
          >
            {settlementLoading ? (
              <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
            ) : settlements.map((row, index) => (
              <button
                key={`${row.ref}:${row.label}`}
                type="button"
                data-nav-scope="waybill-city"
                data-nav-index={index}
                className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
                style={{
                  borderColor: "var(--border)",
                  backgroundColor: index === activeSettlementIndex ? "var(--surface-2)" : "var(--surface)",
                }}
                role="option"
                aria-selected={index === activeSettlementIndex}
                onMouseEnter={() => setActiveSettlementIndex(index)}
                onClick={() => applySettlementSelection(row)}
              >
                {row.label}
              </button>
            ))}
          </div>,
          document.body,
        ) : null}

        {typeof document !== "undefined" && recipientCounterpartyDropdownStyle ? createPortal(
          <div
            ref={recipientCounterpartyDropdownRef}
            className="rounded-md border"
            style={{ ...recipientCounterpartyDropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
            role="listbox"
            aria-label={t("orders.modals.waybill.fields.counterparty")}
          >
            {recipientCounterpartyLoading ? (
              <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
            ) : recipientCounterparties.map((row, index) => {
              const title = (row.label || row.full_name || "").trim() || "—";
              const typeLabel = resolveCounterpartyTypeDisplay(row.counterparty_type);
              const cityLabel = (row.city_label || "").trim();
              const subtitle = [typeLabel, cityLabel].filter(Boolean).join(" • ");
              return (
                <button
                  key={`${row.ref}:${row.counterparty_ref}:${title}`}
                  type="button"
                  data-nav-scope="waybill-recipient-counterparty"
                  data-nav-index={index}
                  className="flex min-h-10 w-full flex-col items-start justify-center gap-0.5 border-b px-3 py-1.5 text-left text-sm last:border-b-0"
                  style={{
                    borderColor: "var(--border)",
                    backgroundColor: index === activeRecipientCounterpartyIndex ? "var(--surface-2)" : "var(--surface)",
                  }}
                  role="option"
                  aria-selected={index === activeRecipientCounterpartyIndex}
                  onMouseEnter={() => setActiveRecipientCounterpartyIndex(index)}
                  onClick={() => applyRecipientCounterpartySelection(row)}
                >
                  <span className="w-full truncate font-medium">{title}</span>
                  {subtitle ? (
                    <span className="w-full truncate text-[11px]" style={{ color: "var(--muted)" }}>
                      {subtitle}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>,
          document.body,
        ) : null}

        {typeof document !== "undefined" && streetDropdownStyle ? createPortal(
          <div
            ref={streetDropdownRef}
            className="rounded-md border"
            style={{ ...streetDropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
            role="listbox"
            aria-label={t("orders.modals.waybill.fields.street")}
          >
            {streetLoading ? (
              <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
            ) : streets.map((row, index) => (
              <button
                key={`${row.street_ref}:${row.label}`}
                type="button"
                data-nav-scope="waybill-street"
                data-nav-index={index}
                className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
                style={{
                  borderColor: "var(--border)",
                  backgroundColor: index === activeStreetIndex ? "var(--surface-2)" : "var(--surface)",
                }}
                role="option"
                aria-selected={index === activeStreetIndex}
                onMouseEnter={() => setActiveStreetIndex(index)}
                onClick={() => {
                  skipNextStreetLookupRef.current = true;
                  setStreetQuery(row.label);
                  setStreets([]);
                  setActiveStreetIndex(-1);
                  setPayload((prev) => ({ ...prev, recipient_street_ref: row.street_ref, recipient_street_label: row.label }));
                }}
              >
                {row.label}
              </button>
            ))}
          </div>,
          document.body,
        ) : null}

        {typeof document !== "undefined" && warehouseDropdownStyle ? createPortal(
          <div
            ref={warehouseDropdownRef}
            className="rounded-md border"
            style={{ ...warehouseDropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
            role="listbox"
            aria-label={t("orders.modals.waybill.fields.warehouse")}
          >
            {warehouseLoading ? (
              <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
            ) : warehouses.map((row, index) => (
              <button
                key={`${row.kind}:${row.ref}:${row.label}`}
                type="button"
                data-nav-scope="waybill-warehouse"
                data-nav-index={index}
                className="flex min-h-10 w-full flex-col items-start justify-center gap-0.5 border-b px-3 py-1.5 text-left text-sm last:border-b-0"
                style={{
                  borderColor: "var(--border)",
                  backgroundColor: index === activeWarehouseIndex ? "var(--surface-2)" : "var(--surface)",
                }}
                role="option"
                aria-selected={index === activeWarehouseIndex}
                onMouseEnter={() => setActiveWarehouseIndex(index)}
                onClick={() => applyWarehouseSuggestionSelection(row)}
              >
                <span className="w-full truncate font-medium">{row.label}</span>
                {row.subtitle ? (
                  <span className="w-full truncate text-[11px]" style={{ color: "var(--muted)" }}>
                    {row.subtitle}
                  </span>
                ) : null}
              </button>
            ))}
          </div>,
          document.body,
        ) : null}

        {typeof document !== "undefined" && packingsDropdownStyle ? createPortal(
          <div
            ref={packingsDropdownRef}
            className="rounded-md border"
            style={{ ...packingsDropdownStyle, borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)", overflowY: "auto" }}
            role="listbox"
            aria-label={t("orders.modals.waybill.fields.packRef")}
          >
            {packingsLoading ? (
              <p className="flex h-10 items-center px-3 text-sm" style={{ color: "var(--muted)" }}>
                {t("orders.modals.waybill.fields.packRefLoading")}
              </p>
            ) : visiblePackings.map((item) => {
              const isActive = selectedPackRefs.includes(item.ref);
              return (
                <button
                  key={item.ref}
                  type="button"
                  className="flex min-h-10 w-full items-center border-b px-3 py-1.5 text-left text-sm last:border-b-0"
                  style={{
                    borderColor: "var(--border)",
                    backgroundColor: isActive ? "var(--surface-2)" : "var(--surface)",
                  }}
                  role="option"
                  aria-selected={isActive}
                  onClick={() => togglePackagingSelection(item)}
                >
                  <span className="w-full truncate">{item.label || item.ref}</span>
                </button>
              );
            })}
          </div>,
          document.body,
        ) : null}

        <footer className="border-t px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1">
              {waybill ? (
                <BackofficeTooltip content={t("orders.modals.waybill.actions.delete")} placement="top" align="center" wrapperClassName="inline-flex">
                  <button
                    type="button"
                    className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
                    style={{ borderColor: "#ef4444", backgroundColor: "rgba(239,68,68,.08)", color: "#b91c1c" }}
                    disabled={isBusy}
                    onClick={onDelete}
                    aria-label={t("orders.modals.waybill.actions.delete")}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </BackofficeTooltip>
              ) : null}

              <button
                type="button"
                className="h-10 rounded-md border px-4 text-xs font-semibold"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                disabled={isBusy || !waybill}
                onClick={onRefresh}
              >
                {t("orders.modals.waybill.actions.checkReaddress")}
              </button>
              <button
                type="button"
                className="h-10 rounded-md border px-4 text-xs font-semibold"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                disabled={isBusy || !waybill}
                onClick={onRefresh}
              >
                {t("orders.modals.waybill.actions.checkReturn")}
              </button>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-1">
              <button
                type="button"
                className="h-10 rounded-md border px-4 text-xs font-semibold"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                disabled={isBusy || !waybill}
                onClick={onSync}
              >
                {t("orders.modals.waybill.actions.trackTtn")}
              </button>
              <button
                type="button"
                className="h-10 rounded-md border px-4 text-xs font-semibold"
                style={{ borderColor: "#d4d4d8", backgroundColor: "#f4f4f5", color: "#3f3f46" }}
                disabled={isBusy || !waybill}
                onClick={() => onPrint("html")}
              >
                {t("orders.modals.waybill.actions.printHtml")}
              </button>
              <button
                type="button"
                className="h-10 rounded-md border px-4 text-xs font-semibold"
                style={{ borderColor: "#52525b", backgroundColor: "#52525b", color: "#fafafa" }}
                disabled={isBusy || !waybill}
                onClick={() => onPrint("pdf")}
              >
                {t("orders.modals.waybill.actions.printPdf")}
              </button>
              <button
                type="button"
                className="h-10 rounded-md border px-4 text-xs font-semibold"
                style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
                disabled={!canSubmit}
                onClick={() => onSave(payloadForSave)}
                title={isReadonlyDocument ? t("orders.modals.waybill.meta.readonlyHint") : undefined}
              >
                {isSubmitting ? t("loading") : waybill ? t("orders.modals.waybill.actions.update") : t("orders.modals.waybill.actions.create")}
              </button>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
