import type { Translator } from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type { BackofficeNovaPoshtaSenderProfile } from "@/features/backoffice/types/nova-poshta.types";

const DRAFT_SENDER_NAME = "Черновик отправителя";

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

export function resolveEffectiveSenderType(
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

export function resolveSenderPreview(): { payer: string; payment: string } {
  return { payer: "Recipient", payment: "Cash" };
}

type SenderPaymentCapabilities = {
  canAfterpaymentOnGoodsCost: boolean | null;
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

export function resolveSenderPaymentCapabilities(
  sender: BackofficeNovaPoshtaSenderProfile | undefined,
): SenderPaymentCapabilities {
  if (!sender) {
    return {
      canAfterpaymentOnGoodsCost: null,
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

  const canAfterpaymentOnGoodsCost = parseCapabilityBoolean(
    options.CanAfterpaymentOnGoodsCost
      ?? normalizedMeta.CanAfterpaymentOnGoodsCost
      ?? normalizedMeta.can_afterpayment_on_goods_cost,
  );
  const canNonCashPayment = parseCapabilityBoolean(
    options.CanNonCashPayment ?? normalizedMeta.CanNonCashPayment ?? normalizedMeta.can_non_cash_payment,
  );
  const canPayThirdPerson = parseCapabilityBoolean(
    options.CanPayTheThirdPerson ?? normalizedMeta.CanPayTheThirdPerson ?? normalizedMeta.can_pay_the_third_person,
  );

  return {
    canAfterpaymentOnGoodsCost,
    canNonCashPayment,
    canPayThirdPerson,
  };
}

export function resolveSenderDisplayName(sender: BackofficeNovaPoshtaSenderProfile | undefined): string {
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

export function isSenderRefLike(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) {
    return false;
  }
  if (/^pending-[\w-]+$/i.test(normalized)) {
    return true;
  }
  return /^[0-9A-Za-z]{8}-[0-9A-Za-z]{4}-[0-9A-Za-z]{4}-[0-9A-Za-z]{4}-[0-9A-Za-z]{12}$/.test(normalized);
}

export function resolveCounterpartyTypeDisplay(rawValue: string): string {
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

export function normalizeCounterpartyType(rawValue: string | null | undefined): "private_person" | "fop" | "business" | "unknown" {
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

export function normalizeCounterpartyBusinessCode(rawValue: string): string {
  return String(rawValue || "").replace(/\D+/g, "");
}

export function isCounterpartyBusinessCodeQuery(rawValue: string): boolean {
  const code = normalizeCounterpartyBusinessCode(rawValue);
  return code.length === 8 || code.length === 10;
}

export function getSenderMetaLabel(sender: BackofficeNovaPoshtaSenderProfile | undefined, key: string): string {
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

export function resolvePayerTypeLabel(value: "Sender" | "Recipient" | "ThirdPerson", t: Translator): string {
  if (value === "Sender") {
    return t("orders.modals.waybill.meta.payerTypes.sender");
  }
  if (value === "ThirdPerson") {
    return t("orders.modals.waybill.meta.payerTypes.thirdPerson");
  }
  return t("orders.modals.waybill.meta.payerTypes.recipient");
}

export function resolvePaymentMethodLabel(value: "Cash" | "NonCash", t: Translator): string {
  if (value === "NonCash") {
    return t("orders.modals.waybill.meta.paymentMethods.nonCash");
  }
  return t("orders.modals.waybill.meta.paymentMethods.cash");
}

export function resolveTimeIntervalFallbackLabel(number: string, t: Translator): string {
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
