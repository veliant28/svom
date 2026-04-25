import type { BackofficeNovaPoshtaLookupWarehouse } from "@/features/backoffice/types/nova-poshta.types";

export type ModalAddressSuggestion = {
  kind: "warehouse" | "street";
  ref: string;
  label: string;
  subtitle: string;
};

export const LETTER_QUERY_WAREHOUSE_LIMIT = 8;
export const DRAFT_SENDER_NAME = "Черновик отправителя";

export type SenderTypeValue = "private_person" | "fop" | "business";

export const EMPTY_SENDER_FORM = {
  api_token: "",
  counterparty_ref: "",
  address_ref: "",
  city_ref: "",
  phone: "",
  contact_name: "",
  is_active: true,
  is_default: false,
};

export type NovaPoshtaSenderFormState = typeof EMPTY_SENDER_FORM;

export function normalizeSenderTypeHint(value: string | null | undefined): SenderTypeValue | "unknown" {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "unknown";
  }
  const compact = normalized.replace(/[\s_-]+/g, "");
  if (normalized.includes("фоп") || normalized.includes("флп") || compact.includes("fop")) {
    return "fop";
  }
  if (
    normalized.includes("organization")
    || normalized.includes("company")
    || compact.includes("business")
    || compact.includes("legalentity")
  ) {
    return "business";
  }
  if (
    normalized === "private_person"
    || compact.includes("privateperson")
    || compact.includes("privatperson")
    || compact.includes("physicalperson")
  ) {
    return "private_person";
  }
  return "unknown";
}

export function resolveSenderTypeFromHints(...values: Array<string | null | undefined>): SenderTypeValue {
  let hasPrivatePerson = false;
  for (const value of values) {
    const normalized = normalizeSenderTypeHint(value);
    if (normalized === "fop" || normalized === "business") {
      return normalized;
    }
    if (normalized === "private_person") {
      hasPrivatePerson = true;
    }
  }
  return hasPrivatePerson ? "private_person" : "private_person";
}

export function isUuidLike(value: string): boolean {
  return /^[0-9A-Za-z]{8}-[0-9A-Za-z]{4}-[0-9A-Za-z]{4}-[0-9A-Za-z]{4}-[0-9A-Za-z]{12}$/.test(value.trim());
}

export function isPendingRefLike(value: string): boolean {
  return /^pending-[\w-]+$/i.test(value.trim());
}

export function isRefLike(value: string): boolean {
  const normalized = value.trim();
  return isUuidLike(normalized) || isPendingRefLike(normalized);
}

export function getRawMetaString(meta: Record<string, unknown> | null | undefined, key: string): string {
  if (!meta || typeof meta !== "object") {
    return "";
  }
  const value = meta[key];
  return typeof value === "string" ? value.trim() : "";
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

export function scrollDropdownOptionIntoView(
  root: HTMLDivElement | null,
  scope: string,
  index: number,
) {
  if (!root || index < 0) {
    return;
  }
  const option = root.querySelector<HTMLElement>(`[data-nav-scope="${scope}"][data-nav-index="${index}"]`);
  option?.scrollIntoView({ block: "nearest" });
}
