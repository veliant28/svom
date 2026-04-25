export type Translator = (key: string, values?: Record<string, string | number>) => string;

export type ActionKind = "confirm" | "ready" | "ship" | "complete" | "reset" | "cancel";

export function extractLabel(sentence: string): string {
  const [label] = sentence.split(":");
  return label.trim();
}

export function humanizeCode(value: string): string {
  if (!value) {
    return "-";
  }

  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .trim();
}

export function resolvePaymentMethodLabel(value: string, t: Translator): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  if (normalized === "cash_on_delivery") {
    return t("orders.payment.values.methods.cash_on_delivery");
  }
  if (normalized === "monobank") {
    return t("orders.payment.values.methods.monobank");
  }
  if (normalized === "liqpay") {
    return t("orders.payment.values.methods.liqpay");
  }
  if (normalized === "card_placeholder") {
    return t("orders.payment.values.methods.card_placeholder");
  }
  return humanizeCode(value);
}

export function resolvePaymentStatusLabel(value: string, t: Translator): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  if (normalized === "pending") {
    return t("orders.payment.values.statuses.pending");
  }
  if (normalized === "processing") {
    return t("orders.payment.values.statuses.processing");
  }
  if (normalized === "created") {
    return t("orders.payment.values.statuses.created");
  }
  if (normalized === "success") {
    return t("orders.payment.values.statuses.success");
  }
  if (normalized === "paid") {
    return t("orders.payment.values.statuses.paid");
  }
  if (normalized === "failed") {
    return t("orders.payment.values.statuses.failed");
  }
  if (normalized === "expired") {
    return t("orders.payment.values.statuses.expired");
  }
  if (normalized === "cancelled" || normalized === "canceled") {
    return t("orders.payment.values.statuses.cancelled");
  }
  return humanizeCode(value);
}

export function resolveDeliveryMethodLabel(value: string, t: Translator): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  if (normalized === "pickup") {
    return t("orders.modals.view.summary.values.deliveryMethods.pickup");
  }
  if (normalized === "courier") {
    return t("orders.modals.view.summary.values.deliveryMethods.courier");
  }
  if (normalized === "nova_poshta") {
    return t("orders.modals.view.summary.values.deliveryMethods.nova_poshta");
  }
  return humanizeCode(value);
}

export function resolveOrderPaymentMethodLabel(value: string, t: Translator): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  if (normalized === "cash_on_delivery") {
    return t("orders.payment.values.methods.cash_on_delivery");
  }
  if (normalized === "monobank") {
    return t("orders.payment.values.methods.monobank");
  }
  if (normalized === "liqpay") {
    return t("orders.payment.values.methods.liqpay");
  }
  if (normalized === "card_placeholder") {
    return t("orders.payment.values.methods.card_placeholder");
  }
  return humanizeCode(value);
}

function looksLikeRegionToken(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return false;
  }

  if (normalized.includes("область")) {
    return true;
  }

  return (
    normalized.endsWith("обл")
    || normalized.endsWith("обл.")
    || normalized.endsWith("ская")
    || normalized.endsWith("ська")
    || normalized.endsWith("ский")
    || normalized.endsWith("ський")
  );
}

function formatCityWithRegion(city: string, region: string): string {
  const normalizedCity = city.trim();
  const normalizedRegion = region.trim();
  if (!normalizedCity && !normalizedRegion) {
    return "";
  }
  if (!normalizedRegion) {
    return normalizedCity;
  }
  if (!normalizedCity) {
    return normalizedRegion;
  }
  if (/^(г\.|м\.)\s*/i.test(normalizedCity)) {
    return `${normalizedCity}, ${normalizedRegion}`;
  }
  return `г. ${normalizedCity}, ${normalizedRegion}`;
}

function splitDeliveryAddress(rawValue: string): { city: string; destination: string; region: string } {
  const raw = rawValue.trim();
  if (!raw) {
    return { city: "", destination: "", region: "" };
  }

  const parts = raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) {
    return { city: "", destination: "", region: "" };
  }

  if (parts.length >= 3) {
    if (looksLikeRegionToken(parts[0])) {
      return {
        city: parts[1] || "",
        destination: parts.slice(2).join(", ").trim(),
        region: parts[0] || "",
      };
    }
    if (looksLikeRegionToken(parts[1])) {
      return {
        city: parts[0] || "",
        destination: parts.slice(2).join(", ").trim(),
        region: parts[1] || "",
      };
    }
  }

  let cityIndex = 0;
  let destinationStartIndex = 1;
  if (parts.length > 1 && looksLikeRegionToken(parts[0])) {
    cityIndex = 1;
    destinationStartIndex = 2;
  }

  return {
    city: parts[cityIndex] || "",
    destination: parts.slice(destinationStartIndex).join(", ").trim(),
    region: parts.length > 1 && looksLikeRegionToken(parts[0]) ? parts[0] : "",
  };
}

function normalizeDeliveryDestination(rawDestination: string, city: string): string {
  const raw = rawDestination.trim();
  if (!raw) {
    return "";
  }

  const parts = raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) {
    return "";
  }

  const normalizedCity = city.trim().toLowerCase();
  const normalizedCityWithoutPrefix = normalizedCity.replace(/^(г\.|м\.)\s*/i, "").trim();
  while (parts.length) {
    const head = parts[0].toLowerCase();
    const isRegionHead = looksLikeRegionToken(parts[0]);
    const isCityHead =
      (normalizedCity && head === normalizedCity)
      || (normalizedCityWithoutPrefix && head === normalizedCityWithoutPrefix);
    if (!isRegionHead && !isCityHead) {
      break;
    }
    parts.shift();
  }

  return parts.join(", ").trim();
}

function looksLikeNovaPoshtaPointToken(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  return /(відділен|отделен|поштомат|почтомат|постомат|адрес|адреса|address)/i.test(normalized);
}

function normalizeCityCandidates(value: string): string[] {
  const raw = value.trim().toLowerCase();
  if (!raw) {
    return [];
  }
  const head = raw.split(",")[0]?.trim() || "";
  const withoutPrefix = head.replace(/^(г\.|м\.)\s*/i, "").trim();
  return [head, withoutPrefix].filter(Boolean);
}

function formatNovaPoshtaDestination(rawDestination: string, city: string, t: Translator): string {
  const normalized = rawDestination.trim();
  if (!normalized) {
    return "";
  }

  const parts = normalized
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) {
    return "";
  }

  const cityCandidates = normalizeCityCandidates(city);
  let pointToken = "";
  if (looksLikeNovaPoshtaPointToken(parts[0])) {
    pointToken = parts.shift() || "";
  }

  while (parts.length && looksLikeRegionToken(parts[0])) {
    parts.shift();
  }
  while (parts.length && cityCandidates.includes(parts[0].toLowerCase())) {
    parts.shift();
  }

  if (!pointToken && parts.length && looksLikeNovaPoshtaPointToken(parts[0])) {
    pointToken = parts.shift() || "";
  }

  const tail = parts.join(", ").trim();
  const warehouseLabel = t("orders.modals.waybill.delivery.warehouse");
  const resolvedPointToken = pointToken || warehouseLabel;
  return [resolvedPointToken, tail].filter(Boolean).join(", ");
}

export function resolveDeliveryAddressParts(
  order: {
    delivery_address?: string;
    delivery_city_label?: string;
    delivery_destination_label?: string;
    delivery_method?: string;
  } | null | undefined,
  t: Translator,
): { city: string; destination: string } {
  const deliveryMethod = (order?.delivery_method || "").trim().toLowerCase();
  if (deliveryMethod === "pickup") {
    return {
      city: "",
      destination: "",
    };
  }

  const cityLabel = (order?.delivery_city_label || "").trim();
  const destinationLabel = (order?.delivery_destination_label || "").trim();
  const fallbackAddress = (order?.delivery_address || "").trim();
  const parsed = splitDeliveryAddress(fallbackAddress);
  const resolvedCity = formatCityWithRegion(cityLabel || parsed.city, parsed.region);
  const rawDestination = destinationLabel || parsed.destination || fallbackAddress;
  const normalizedDestination = normalizeDeliveryDestination(rawDestination, resolvedCity);

  const resolvedDestination = deliveryMethod === "nova_poshta"
    ? formatNovaPoshtaDestination(rawDestination, resolvedCity, t) || normalizedDestination
    : normalizedDestination;

  return {
    city: resolvedCity || "-",
    destination: resolvedDestination || "-",
  };
}

export function selectedActionForStatus(status: string, canResetToNew = false): ActionKind {
  const normalized = status.trim().toLowerCase();
  if (normalized === "new") {
    return "reset";
  }
  if (normalized === "processing") {
    return "confirm";
  }
  if (normalized === "ready_for_shipment") {
    return "ready";
  }
  if (normalized === "shipped") {
    return "ship";
  }
  if (normalized === "completed") {
    return "complete";
  }
  if (normalized === "cancelled") {
    return "cancel";
  }
  const [first] = availableActionsForStatus(status, canResetToNew);
  return first ?? "confirm";
}

export function availableActionsForStatus(status: string, canResetToNew = false): ActionKind[] {
  if (canResetToNew) {
    return ["reset", "confirm", "ready", "ship", "complete", "cancel"];
  }

  const normalized = status.trim().toLowerCase();
  if (normalized === "new") {
    return ["confirm", "cancel"];
  }
  if (normalized === "processing") {
    return ["ready", "cancel"];
  }
  if (normalized === "ready_for_shipment") {
    return ["ship", "cancel"];
  }
  if (normalized === "shipped") {
    return ["complete"];
  }
  return [];
}
