import type {
  CheckoutNovaPoshtaSettlement,
  CheckoutNovaPoshtaStreet,
  CheckoutNovaPoshtaWarehouse,
} from "@/features/checkout/api/lookup-nova-poshta";
import type { Order } from "@/features/commerce/types";

export type CheckoutDeliveryOption = "pickup" | "nova_poshta_warehouse" | "nova_poshta_courier";

export const CITY_LOOKUP_MIN_QUERY_LENGTH = 2;
export const STREET_LOOKUP_MIN_QUERY_LENGTH = 2;

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

export function resolveNpLocale(locale: string): "uk" | "ru" {
  const normalized = locale.toLowerCase();
  if (normalized.startsWith("ru")) {
    return "ru";
  }
  return "uk";
}

export function resolveEffectiveDeliveryMethod(deliveryOption: CheckoutDeliveryOption): Order["delivery_method"] {
  if (deliveryOption === "pickup") {
    return "pickup";
  }
  if (deliveryOption === "nova_poshta_warehouse") {
    return "nova_poshta";
  }
  return "courier";
}

function resolveWarehouseTypeLabel(locale: string, isPostomat: boolean): string {
  const localeIsRu = (locale || "").toLowerCase().startsWith("ru");
  if (isPostomat) {
    return localeIsRu ? "Почтомат" : "Поштомат";
  }
  return localeIsRu ? "Отделение" : "Відділення";
}

export function isPostomatWarehouse(item: CheckoutNovaPoshtaWarehouse): boolean {
  const normalizedCategory = String(item.category || "").toLowerCase();
  const normalizedType = String(item.type || "").toLowerCase();
  const normalizedText = `${item.description || ""} ${item.full_description || ""} ${item.label || ""}`.toLowerCase();
  return (
    normalizedCategory.includes("postomat")
    || normalizedType.includes("postomat")
    || normalizedType.includes("поштомат")
    || normalizedType.includes("постомат")
    || normalizedType.includes("почтомат")
    || normalizedText.includes("поштомат")
    || normalizedText.includes("постомат")
    || normalizedText.includes("почтомат")
  );
}

export function formatWarehouseLookupDisplay(item: CheckoutNovaPoshtaWarehouse, locale: string): { label: string; subtitle: string } {
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
  const isPostomat = isPostomatWarehouse(item);
  const typeLabel = resolveWarehouseTypeLabel(locale, isPostomat);
  const fallbackLabel = normalizedNumber ? `${typeLabel} №${normalizedNumber}` : typeLabel;
  const normalizedPrefix = descriptionPrefix.replace(/\s+/g, " ").trim();
  const prefixHasType = /(відділен|отделен|поштомат|почтомат|постомат|department|branch)/i.test(normalizedPrefix);
  const prefixHasNumber = /№\s*\d+|\b\d{1,5}\b/.test(normalizedPrefix);
  const numberToken = normalizedNumber ? `№${normalizedNumber}` : "";
  let normalizedLabel = normalizedPrefix || fallbackLabel;
  if (!prefixHasType && (prefixHasNumber || numberToken)) {
    normalizedLabel = `${typeLabel} ${normalizedPrefix || numberToken}`.trim();
  } else if (!normalizedLabel) {
    normalizedLabel = fallbackLabel;
  }
  return {
    label: normalizedLabel,
    subtitle: fallbackStreet,
  };
}

export function formatWarehouseInputValue(item: CheckoutNovaPoshtaWarehouse, locale: string): string {
  const display = formatWarehouseLookupDisplay(item, locale);
  return [display.label, display.subtitle].filter(Boolean).join(", ");
}

export function resolveCheckoutDeliveryAddress({
  deliveryOption,
  selectedCity,
  cityQuery,
  selectedWarehouse,
  warehouseQuery,
  selectedStreet,
  streetQuery,
  house,
  apartment,
  npLocale,
}: {
  deliveryOption: CheckoutDeliveryOption;
  selectedCity: CheckoutNovaPoshtaSettlement | null;
  cityQuery: string;
  selectedWarehouse: CheckoutNovaPoshtaWarehouse | null;
  warehouseQuery: string;
  selectedStreet: CheckoutNovaPoshtaStreet | null;
  streetQuery: string;
  house: string;
  apartment: string;
  npLocale: string;
}): string {
  if (deliveryOption === "pickup") {
    return "";
  }

  if (deliveryOption === "nova_poshta_warehouse") {
    const cityLabel = selectedCity?.label || cityQuery.trim();
    const destinationLabel = selectedWarehouse
      ? formatWarehouseInputValue(selectedWarehouse, npLocale)
      : warehouseQuery.trim();
    return [cityLabel, destinationLabel].filter(Boolean).join(", ");
  }

  const cityLabel = selectedCity?.label || cityQuery.trim();
  const streetLabel = selectedStreet?.label || streetQuery.trim();
  const houseLabel = house.trim();
  const apartmentLabel = apartment.trim();

  if (!streetLabel && !houseLabel) {
    return cityLabel;
  }

  const streetWithHouse = houseLabel ? `${streetLabel}, ${houseLabel}` : streetLabel;
  const line = apartmentLabel ? `${streetWithHouse}, ${apartmentLabel}` : streetWithHouse;
  return [cityLabel, line].filter(Boolean).join(", ");
}

export function resolveCheckoutDeliverySnapshot({
  deliveryOption,
  selectedCity,
  cityQuery,
  selectedWarehouse,
  warehouseQuery,
  selectedStreet,
  streetQuery,
  house,
  apartment,
  npLocale,
}: {
  deliveryOption: CheckoutDeliveryOption;
  selectedCity: CheckoutNovaPoshtaSettlement | null;
  cityQuery: string;
  selectedWarehouse: CheckoutNovaPoshtaWarehouse | null;
  warehouseQuery: string;
  selectedStreet: CheckoutNovaPoshtaStreet | null;
  streetQuery: string;
  house: string;
  apartment: string;
  npLocale: string;
}): Record<string, unknown> {
  const cityLabel = selectedCity?.label || cityQuery.trim();
  const cityRef = selectedCity?.delivery_city_ref || selectedCity?.ref || "";
  const settlementRef = selectedCity?.settlement_ref || selectedCity?.ref || "";
  const regionLabel = selectedCity?.area || "";
  const areaLabel = selectedCity?.region || "";

  if (deliveryOption === "pickup") {
    return {
      method: "pickup",
    };
  }

  if (deliveryOption === "nova_poshta_warehouse") {
    const destinationLabel = selectedWarehouse
      ? formatWarehouseInputValue(selectedWarehouse, npLocale)
      : warehouseQuery.trim();
    const warehouse = selectedWarehouse ? {
      ref: selectedWarehouse.ref || "",
      number: selectedWarehouse.number || "",
      type: selectedWarehouse.type || "",
      category: selectedWarehouse.category || "",
      label: destinationLabel,
    } : {
      ref: "",
      number: "",
      type: "",
      category: "",
      label: destinationLabel,
    };

    return {
      method: "nova_poshta",
      nova_poshta: {
        delivery_type: selectedWarehouse && isPostomatWarehouse(selectedWarehouse) ? "postomat" : "warehouse",
        city_ref: cityRef,
        city_label: cityLabel,
        settlement_ref: settlementRef,
        region_label: regionLabel,
        area_label: areaLabel,
        destination_ref: selectedWarehouse?.ref || "",
        destination_label: destinationLabel,
        warehouse,
        street: {
          street_ref: "",
          street_label: "",
          house: "",
          apartment: "",
        },
      },
    };
  }

  const streetLabel = selectedStreet?.label || streetQuery.trim();
  const houseLabel = house.trim();
  const apartmentLabel = apartment.trim();
  const streetWithHouse = houseLabel ? `${streetLabel}, ${houseLabel}` : streetLabel;
  const destinationLabel = apartmentLabel ? `${streetWithHouse}, ${apartmentLabel}` : streetWithHouse;
  return {
    method: "courier",
    courier: {
      city_label: cityLabel,
      region_label: regionLabel,
      destination_label: destinationLabel,
      street_ref: selectedStreet?.street_ref || "",
      street_label: streetLabel,
      house: houseLabel,
      apartment: apartmentLabel,
    },
  };
}

export function resolvePromoErrorKey(code: string): string {
  if (code === "not_found") {
    return "notFound";
  }
  if (code === "not_owned") {
    return "notOwned";
  }
  if (code === "expired") {
    return "expired";
  }
  if (code === "used") {
    return "used";
  }
  if (code === "disabled") {
    return "disabled";
  }
  if (code === "delivery_zero") {
    return "deliveryZero";
  }
  if (code === "no_markup") {
    return "noMarkup";
  }
  return "";
}
