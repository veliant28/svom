"use client";

import { Store } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { useLocale, useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { CartSummaryBlock } from "@/features/cart/components/cart-summary-block";
import { useCart } from "@/features/cart/hooks/use-cart";
import { applyCheckoutPromo } from "@/features/checkout/api/apply-checkout-promo";
import { clearCheckoutPromo } from "@/features/checkout/api/clear-checkout-promo";
import { getCheckoutPreview } from "@/features/checkout/api/get-checkout-preview";
import {
  lookupCheckoutNovaPoshtaSettlements,
  lookupCheckoutNovaPoshtaStreets,
  lookupCheckoutNovaPoshtaWarehouses,
  type CheckoutNovaPoshtaSettlement,
  type CheckoutNovaPoshtaStreet,
  type CheckoutNovaPoshtaWarehouse,
} from "@/features/checkout/api/lookup-nova-poshta";
import { getCheckoutMonobankWidget } from "@/features/checkout/api/monobank-payment";
import { submitCheckout } from "@/features/checkout/api/submit-checkout";
import { MonoPayWidget } from "@/features/checkout/components/payment/monopay-widget";
import { PaymentMethodToggle } from "@/features/checkout/components/payment/payment-method-toggle";
import type { CheckoutPaymentMethod, MonobankWidgetResponse } from "@/features/checkout/types/payment";
import type { CheckoutPreview, Order } from "@/features/commerce/types";
import { Link } from "@/i18n/navigation";
import { isApiRequestError } from "@/shared/api/http-client";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";
import {
  PHONE_INPUT_MAX_LENGTH,
  PHONE_INPUT_PLACEHOLDER,
  PHONE_INPUT_REGEX,
  formatPhoneInput,
  isPhoneInputValid,
} from "@/shared/lib/phone-input";

type CheckoutDeliveryOption = "pickup" | "nova_poshta_warehouse" | "nova_poshta_courier";

const CITY_LOOKUP_MIN_QUERY_LENGTH = 2;
const STREET_LOOKUP_MIN_QUERY_LENGTH = 2;

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

function resolveWarehouseTypeLabel(locale: string, isPostomat: boolean): string {
  const localeIsRu = (locale || "").toLowerCase().startsWith("ru");
  if (isPostomat) {
    return localeIsRu ? "Почтомат" : "Поштомат";
  }
  return localeIsRu ? "Отделение" : "Відділення";
}

function isPostomatWarehouse(item: CheckoutNovaPoshtaWarehouse): boolean {
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

function formatWarehouseLookupDisplay(item: CheckoutNovaPoshtaWarehouse, locale: string): { label: string; subtitle: string } {
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

function formatWarehouseInputValue(item: CheckoutNovaPoshtaWarehouse, locale: string): string {
  const display = formatWarehouseLookupDisplay(item, locale);
  return [display.label, display.subtitle].filter(Boolean).join(", ");
}

function resolvePromoErrorKey(code: string): string {
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

export function CheckoutPage() {
  const t = useTranslations("commerce.checkout");
  const locale = useLocale();
  const { token, isAuthenticated, user } = useAuth();
  const { cart, refresh } = useCart();
  const { showApiError, showError, showSuccess } = useStorefrontFeedback();
  const npDestinationParts = t("fields.npDestination")
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean);
  const npDestinationLine1 = npDestinationParts.length > 0 ? `${npDestinationParts[0]}/` : t("fields.npDestination");
  const npDestinationLine2 = npDestinationParts.length > 1 ? npDestinationParts[1] : "";

  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [middleName, setMiddleName] = useState(user?.middle_name ?? "");
  const [phone, setPhone] = useState(formatPhoneInput(user?.phone ?? ""));
  const [isLastNameDirty, setIsLastNameDirty] = useState(false);
  const [isFirstNameDirty, setIsFirstNameDirty] = useState(false);
  const [isMiddleNameDirty, setIsMiddleNameDirty] = useState(false);
  const [isPhoneDirty, setIsPhoneDirty] = useState(false);

  const [deliveryOption, setDeliveryOption] = useState<CheckoutDeliveryOption>("pickup");
  const [cityQuery, setCityQuery] = useState("");
  const [cityOptions, setCityOptions] = useState<CheckoutNovaPoshtaSettlement[]>([]);
  const [cityLoading, setCityLoading] = useState(false);
  const [activeCityIndex, setActiveCityIndex] = useState(-1);
  const [selectedCity, setSelectedCity] = useState<CheckoutNovaPoshtaSettlement | null>(null);

  const [warehouseQuery, setWarehouseQuery] = useState("");
  const [warehouseOptions, setWarehouseOptions] = useState<CheckoutNovaPoshtaWarehouse[]>([]);
  const [warehouseLoading, setWarehouseLoading] = useState(false);
  const [activeWarehouseIndex, setActiveWarehouseIndex] = useState(-1);
  const [selectedWarehouse, setSelectedWarehouse] = useState<CheckoutNovaPoshtaWarehouse | null>(null);

  const [streetQuery, setStreetQuery] = useState("");
  const [streetOptions, setStreetOptions] = useState<CheckoutNovaPoshtaStreet[]>([]);
  const [streetLoading, setStreetLoading] = useState(false);
  const [activeStreetIndex, setActiveStreetIndex] = useState(-1);
  const [selectedStreet, setSelectedStreet] = useState<CheckoutNovaPoshtaStreet | null>(null);

  const [house, setHouse] = useState("");
  const [apartment, setApartment] = useState("");

  const [paymentMethod, setPaymentMethod] = useState<CheckoutPaymentMethod>("monobank");
  const [comment, setComment] = useState("");
  const [monobankWidgetState, setMonobankWidgetState] = useState<MonobankWidgetResponse | null>(null);
  const [monobankWidgetLoading, setMonobankWidgetLoading] = useState(false);
  const [preview, setPreview] = useState<CheckoutPreview | null>(null);
  const [promoInput, setPromoInput] = useState("");
  const [appliedPromoCode, setAppliedPromoCode] = useState("");
  const [isPromoApplying, setIsPromoApplying] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const cityLookupRootRef = useRef<HTMLLabelElement | null>(null);
  const warehouseLookupRootRef = useRef<HTMLLabelElement | null>(null);
  const streetLookupRootRef = useRef<HTMLLabelElement | null>(null);

  useEffect(() => {
    if (!isLastNameDirty) {
      setLastName(user?.last_name ?? "");
    }
    if (!isFirstNameDirty) {
      setFirstName(user?.first_name ?? "");
    }
    if (!isMiddleNameDirty) {
      setMiddleName(user?.middle_name ?? "");
    }
    if (!isPhoneDirty) {
      setPhone(formatPhoneInput(user?.phone ?? ""));
    }
  }, [isLastNameDirty, isMiddleNameDirty, isPhoneDirty, isFirstNameDirty, user?.first_name, user?.last_name, user?.middle_name, user?.phone]);

  useEffect(() => {
    if (paymentMethod !== "monobank") {
      setMonobankWidgetState(null);
    }
  }, [paymentMethod]);

  const npLocale = useMemo(() => {
    const normalized = locale.toLowerCase();
    if (normalized.startsWith("ru")) {
      return "ru";
    }
    return "uk";
  }, [locale]);

  const effectiveDeliveryMethod = useMemo<Order["delivery_method"]>(() => {
    if (deliveryOption === "pickup") {
      return "pickup";
    }
    if (deliveryOption === "nova_poshta_warehouse") {
      return "nova_poshta";
    }
    return "courier";
  }, [deliveryOption]);

  const resolvedDeliveryAddress = useMemo(() => {
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
  }, [apartment, cityQuery, deliveryOption, house, npLocale, selectedCity, selectedStreet, selectedWarehouse, streetQuery, warehouseQuery]);

  const resolvedDeliverySnapshot = useMemo<Record<string, unknown>>(() => {
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
  }, [
    apartment,
    cityQuery,
    deliveryOption,
    house,
    npLocale,
    selectedCity,
    selectedStreet,
    selectedWarehouse,
    streetQuery,
    warehouseQuery,
  ]);

  const contactFullName = useMemo(
    () => [lastName.trim(), firstName.trim(), middleName.trim()].filter(Boolean).join(" "),
    [lastName, middleName, firstName],
  );
  const contactEmail = user?.email ?? "";

  function applyCitySelection(item: CheckoutNovaPoshtaSettlement) {
    setSelectedCity(item);
    setCityQuery(item.label);
    setCityOptions([]);
    setActiveCityIndex(-1);
    setSelectedWarehouse(null);
    setWarehouseQuery("");
    setWarehouseOptions([]);
    setActiveWarehouseIndex(-1);
    setSelectedStreet(null);
    setStreetQuery("");
    setStreetOptions([]);
    setActiveStreetIndex(-1);
  }

  function applyWarehouseSelection(item: CheckoutNovaPoshtaWarehouse) {
    setSelectedWarehouse(item);
    setWarehouseQuery(formatWarehouseInputValue(item, npLocale));
    setWarehouseOptions([]);
    setActiveWarehouseIndex(-1);
  }

  function applyStreetSelection(item: CheckoutNovaPoshtaStreet) {
    setSelectedStreet(item);
    setStreetQuery(item.label);
    setStreetOptions([]);
    setActiveStreetIndex(-1);
  }

  useEffect(() => {
    let isMounted = true;

    async function loadPreview() {
      if (!token || !isAuthenticated) {
        if (isMounted) {
          setPreview(null);
        }
        return;
      }

      try {
        const response = await getCheckoutPreview(token, effectiveDeliveryMethod, appliedPromoCode || undefined);
        if (isMounted) {
          setPreview(response.checkout_preview);
          if (response.checkout_preview.promo?.code) {
            setAppliedPromoCode(response.checkout_preview.promo.code);
            setPromoInput(response.checkout_preview.promo.code);
          }
        }
      } catch (error) {
        if (isMounted) {
          setPreview(null);
          if (appliedPromoCode) {
            setAppliedPromoCode("");
            const apiCode = isApiRequestError(error) ? String(error.payload?.promo_code_error || "") : "";
            const key = resolvePromoErrorKey(apiCode);
            const message = key ? t(`promo.errors.${key}`) : t("promo.messages.applyInvalidated");
            showApiError(error, message);
          }
        }
      }
    }

    void loadPreview();

    return () => {
      isMounted = false;
    };
  }, [token, isAuthenticated, effectiveDeliveryMethod, cart?.updated_at, appliedPromoCode, showApiError, t]);

  useEffect(() => {
    if (!token || !isAuthenticated || deliveryOption === "pickup") {
      setCityOptions([]);
      setActiveCityIndex(-1);
      setCityLoading(false);
      return;
    }

    const query = cityQuery.trim();
    if (selectedCity && query === selectedCity.label.trim()) {
      setCityOptions([]);
      setActiveCityIndex(-1);
      setCityLoading(false);
      return;
    }

    if (query.length < CITY_LOOKUP_MIN_QUERY_LENGTH) {
      setCityOptions([]);
      setActiveCityIndex(-1);
      setCityLoading(false);
      return;
    }

    let isMounted = true;
    setCityLoading(true);
    const timeoutId = window.setTimeout(async () => {
      try {
        const response = await lookupCheckoutNovaPoshtaSettlements(token, {
          query,
          locale: npLocale,
        });
        if (!isMounted) {
          return;
        }
        setCityOptions(response.results);
        setActiveCityIndex(response.results.length > 0 ? 0 : -1);
      } catch {
        if (isMounted) {
          setCityOptions([]);
          setActiveCityIndex(-1);
        }
      } finally {
        if (isMounted) {
          setCityLoading(false);
        }
      }
    }, 260);

    return () => {
      isMounted = false;
      window.clearTimeout(timeoutId);
    };
  }, [cityQuery, deliveryOption, isAuthenticated, npLocale, selectedCity, token]);

  useEffect(() => {
    if (!token || !isAuthenticated || deliveryOption !== "nova_poshta_warehouse" || !selectedCity) {
      setWarehouseOptions([]);
      setActiveWarehouseIndex(-1);
      setWarehouseLoading(false);
      return;
    }

    const query = warehouseQuery.trim();
    if (selectedWarehouse && query === formatWarehouseInputValue(selectedWarehouse, npLocale).trim()) {
      setWarehouseOptions([]);
      setActiveWarehouseIndex(-1);
      setWarehouseLoading(false);
      return;
    }

    let isMounted = true;
    setWarehouseLoading(true);
    const timeoutId = window.setTimeout(async () => {
      try {
        const response = await lookupCheckoutNovaPoshtaWarehouses(token, {
          city_ref: selectedCity.delivery_city_ref || selectedCity.ref,
          query,
          locale: npLocale,
        });
        if (!isMounted) {
          return;
        }
        setWarehouseOptions(response.results);
        setActiveWarehouseIndex(response.results.length > 0 ? 0 : -1);
      } catch {
        if (isMounted) {
          setWarehouseOptions([]);
          setActiveWarehouseIndex(-1);
        }
      } finally {
        if (isMounted) {
          setWarehouseLoading(false);
        }
      }
    }, 260);

    return () => {
      isMounted = false;
      window.clearTimeout(timeoutId);
    };
  }, [deliveryOption, isAuthenticated, npLocale, selectedCity, selectedWarehouse, token, warehouseQuery]);

  useEffect(() => {
    if (!token || !isAuthenticated || deliveryOption !== "nova_poshta_courier" || !selectedCity) {
      setStreetOptions([]);
      setActiveStreetIndex(-1);
      setStreetLoading(false);
      return;
    }

    const query = streetQuery.trim();
    if (selectedStreet && query === selectedStreet.label.trim()) {
      setStreetOptions([]);
      setActiveStreetIndex(-1);
      setStreetLoading(false);
      return;
    }

    if (query.length < STREET_LOOKUP_MIN_QUERY_LENGTH) {
      setStreetOptions([]);
      setActiveStreetIndex(-1);
      setStreetLoading(false);
      return;
    }

    let isMounted = true;
    setStreetLoading(true);
    const timeoutId = window.setTimeout(async () => {
      try {
        const response = await lookupCheckoutNovaPoshtaStreets(token, {
          settlement_ref: selectedCity.settlement_ref || selectedCity.ref,
          query,
          locale: npLocale,
        });
        if (!isMounted) {
          return;
        }
        setStreetOptions(response.results);
        setActiveStreetIndex(response.results.length > 0 ? 0 : -1);
      } catch {
        if (isMounted) {
          setStreetOptions([]);
          setActiveStreetIndex(-1);
        }
      } finally {
        if (isMounted) {
          setStreetLoading(false);
        }
      }
    }, 260);

    return () => {
      isMounted = false;
      window.clearTimeout(timeoutId);
    };
  }, [deliveryOption, isAuthenticated, npLocale, selectedCity, selectedStreet, streetQuery, token]);

  useEffect(() => {
    if (!cityOptions.length || activeCityIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(cityLookupRootRef.current, "checkout-city", activeCityIndex);
  }, [activeCityIndex, cityOptions.length]);

  useEffect(() => {
    if (!warehouseOptions.length || activeWarehouseIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(warehouseLookupRootRef.current, "checkout-warehouse", activeWarehouseIndex);
  }, [activeWarehouseIndex, warehouseOptions.length]);

  useEffect(() => {
    if (!streetOptions.length || activeStreetIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(streetLookupRootRef.current, "checkout-street", activeStreetIndex);
  }, [activeStreetIndex, streetOptions.length]);

  function resolvePromoErrorMessage(error: unknown, fallback: string): string {
    if (!isApiRequestError(error)) {
      return fallback;
    }
    const apiCode = String(error.payload?.promo_code_error || "");
    const key = resolvePromoErrorKey(apiCode);
    if (!key) {
      return fallback;
    }
    return t(`promo.errors.${key}`);
  }

  async function handleApplyPromo() {
    const normalized = promoInput.trim();
    if (!token || !normalized) {
      return;
    }

    setIsPromoApplying(true);
    try {
      const response = await applyCheckoutPromo(token, {
        promo_code: normalized,
        delivery_method: effectiveDeliveryMethod,
      });
      setPreview(response.checkout_preview);
      const code = response.checkout_preview.promo?.code || normalized;
      setAppliedPromoCode(code);
      setPromoInput(code);
      showSuccess(t("promo.messages.applied"));
    } catch (error) {
      showApiError(error, resolvePromoErrorMessage(error, t("promo.messages.applyFailed")));
    } finally {
      setIsPromoApplying(false);
    }
  }

  async function handleClearPromo() {
    if (!token) {
      return;
    }

    setIsPromoApplying(true);
    try {
      const response = await clearCheckoutPromo(token, {
        delivery_method: effectiveDeliveryMethod,
      });
      setPreview(response.checkout_preview);
      setAppliedPromoCode("");
      setPromoInput("");
      showSuccess(t("promo.messages.cleared"));
    } catch (error) {
      showApiError(error, t("promo.messages.clearFailed"));
    } finally {
      setIsPromoApplying(false);
    }
  }

  if (!isAuthenticated) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("authRequired")}
        </p>
        <Link href="/login" className="mt-4 inline-flex rounded-md border px-3 py-2 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          {t("goToLogin")}
        </Link>
      </section>
    );
  }

  if (!cart || cart.items.length === 0) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("emptyCart")}
        </p>
        <Link href="/catalog" className="mt-4 inline-flex rounded-md border px-3 py-2 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          {t("goToCatalog")}
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      {(preview?.warnings?.length ?? 0) > 0 ? (
        <div className="mt-3 rounded-xl border px-3 py-2 text-sm" style={{ borderColor: "var(--danger, #b42318)", backgroundColor: "color-mix(in srgb, var(--danger, #b42318) 8%, transparent)" }}>
          {preview?.warnings.map((warning) => (
            <p key={warning.product_id}>
              {warning.product_name}: {warning.warning}
            </p>
          ))}
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_320px]">
        <form
          className="rounded-xl border p-4"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          onSubmit={async (event) => {
            event.preventDefault();
            if (!token) {
              return;
            }
            if (!isPhoneInputValid(phone)) {
              showError(t("phoneFormatError"));
              return;
            }
            if (deliveryOption !== "pickup" && !selectedCity) {
              showError(t("errors.deliveryCityRequired"));
              return;
            }
            if (deliveryOption === "nova_poshta_warehouse" && !selectedWarehouse) {
              showError(t("errors.deliveryDestinationRequired"));
              return;
            }
            if (deliveryOption === "nova_poshta_courier" && (!selectedStreet || !house.trim())) {
              showError(t("errors.deliveryStreetRequired"));
              return;
            }
            if (paymentMethod === "novapay") {
              showError(t("payment.novapayComingSoon"));
              return;
            }

            setIsSubmitting(true);
            try {
              const order = await submitCheckout(token, {
                contact_full_name: contactFullName,
                contact_phone: phone,
                contact_email: contactEmail,
                delivery_method: effectiveDeliveryMethod,
                delivery_address: resolvedDeliveryAddress,
                delivery_snapshot: resolvedDeliverySnapshot,
                payment_method: paymentMethod,
                customer_comment: comment,
                promo_code: appliedPromoCode || undefined,
              });
              showSuccess(t("success", { orderNumber: order.order_number }));
              await refresh();
              setAppliedPromoCode("");
              setPromoInput("");
              if (paymentMethod === "monobank") {
                const checkoutPageUrl = (order.payment?.page_url || "").trim();
                if (checkoutPageUrl) {
                  window.location.assign(checkoutPageUrl);
                  return;
                }

                setMonobankWidgetLoading(true);
                try {
                  const widgetPayload = await getCheckoutMonobankWidget(token, order.id);
                  setMonobankWidgetState(widgetPayload);
                  const widgetPageUrl = (widgetPayload.page_url || "").trim();
                  if (widgetPageUrl) {
                    window.location.assign(widgetPageUrl);
                    return;
                  }
                } catch (widgetError) {
                  showApiError(widgetError, t("payment.widgetFailedFallback"));
                  setMonobankWidgetState({
                    order_id: order.id,
                    invoice_id: order.payment?.invoice_id || "",
                    page_url: order.payment?.page_url || "",
                    widget: null,
                  });
                } finally {
                  setMonobankWidgetLoading(false);
                }
              } else if (paymentMethod === "liqpay") {
                const checkoutPageUrl = (order.payment?.page_url || "").trim();
                if (checkoutPageUrl) {
                  window.location.assign(checkoutPageUrl);
                  return;
                }
                showError(t("payment.liqpayPageUnavailable"));
                setMonobankWidgetState(null);
              } else {
                setMonobankWidgetState(null);
              }
            } catch (submitError) {
              showApiError(submitError, t("submitError"));
            } finally {
              setIsSubmitting(false);
            }
          }}
        >
          <h2 className="text-lg font-semibold">{t("sections.contact")}</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div className="grid gap-3">
              <label className="flex flex-col gap-1 text-xs">
                {t("fields.lastName")}
                <input
                  value={lastName}
                  onChange={(event) => {
                    setIsLastNameDirty(true);
                    setLastName(event.target.value);
                  }}
                  required
                  className="h-10 rounded-md border px-3"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                {t("fields.firstName")}
                <input
                  value={firstName}
                  onChange={(event) => {
                    setIsFirstNameDirty(true);
                    setFirstName(event.target.value);
                  }}
                  required
                  className="h-10 rounded-md border px-3"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                />
              </label>
            </div>
            <div className="grid gap-3">
              <label className="flex flex-col gap-1 text-xs">
                {t("fields.middleName")}
                <input
                  value={middleName}
                  onChange={(event) => {
                    setIsMiddleNameDirty(true);
                    setMiddleName(event.target.value);
                  }}
                  className="h-10 rounded-md border px-3"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                {t("fields.phone")}
                <input
                  value={phone}
                  onChange={(event) => {
                    setIsPhoneDirty(true);
                    setPhone(formatPhoneInput(event.target.value));
                  }}
                  required
                  placeholder={PHONE_INPUT_PLACEHOLDER}
                  inputMode="numeric"
                  pattern={PHONE_INPUT_REGEX.source}
                  maxLength={PHONE_INPUT_MAX_LENGTH}
                  title={PHONE_INPUT_PLACEHOLDER}
                  className="h-10 rounded-md border px-3"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                />
              </label>
            </div>
          </div>

          <h2 className="mt-5 text-lg font-semibold">{t("sections.delivery")}</h2>
          <div className="mt-3 grid gap-3">
            <div className="grid gap-2 sm:grid-cols-3">
              <button
                type="button"
                className="inline-flex h-[3.75rem] items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold"
                style={{
                  borderColor: deliveryOption === "pickup" ? "var(--accent)" : "var(--border)",
                  backgroundColor: deliveryOption === "pickup" ? "color-mix(in srgb, var(--accent) 12%, var(--surface))" : "var(--surface)",
                }}
                onClick={() => setDeliveryOption("pickup")}
              >
                <Store size={30} className="shrink-0" />
                <span className="leading-tight">{t("deliveryOptions.pickup")}</span>
              </button>
              <button
                type="button"
                className="inline-flex h-[3.75rem] items-center justify-between gap-2 rounded-md border px-3 text-sm font-semibold"
                style={{
                  borderColor: deliveryOption === "nova_poshta_warehouse" ? "var(--accent)" : "var(--border)",
                  backgroundColor: deliveryOption === "nova_poshta_warehouse" ? "color-mix(in srgb, var(--accent) 12%, var(--surface))" : "var(--surface)",
                }}
                onClick={() => setDeliveryOption("nova_poshta_warehouse")}
              >
                <span className="inline-flex min-w-0 items-center gap-2 leading-none">
                  <Image src="/icons/nova-poshta.svg" alt="" width={30} height={30} className="h-[30px] w-[30px] shrink-0" aria-hidden />
                  <span className="whitespace-nowrap">{t("delivery.novaPoshta")}</span>
                </span>
                <span className="shrink-0 text-right leading-[1.05]">
                  <span className="block">{npDestinationLine1}</span>
                  {npDestinationLine2 ? <span className="block">{npDestinationLine2}</span> : null}
                </span>
              </button>
              <button
                type="button"
                className="inline-flex h-[3.75rem] items-center justify-center gap-2 rounded-md border px-3 text-sm font-semibold"
                style={{
                  borderColor: deliveryOption === "nova_poshta_courier" ? "var(--accent)" : "var(--border)",
                  backgroundColor: deliveryOption === "nova_poshta_courier" ? "color-mix(in srgb, var(--accent) 12%, var(--surface))" : "var(--surface)",
                }}
                onClick={() => setDeliveryOption("nova_poshta_courier")}
              >
                <Image src="/icons/nova-poshta.svg" alt="" width={30} height={30} className="h-[30px] w-[30px] shrink-0" aria-hidden />
                <span className="leading-tight">{t("deliveryOptions.novaPoshtaCourier")}</span>
              </button>
            </div>

            {deliveryOption !== "pickup" ? (
              <label ref={cityLookupRootRef} className="relative flex flex-col gap-1 text-xs">
                {t("fields.npCity")}
                <input
                  value={cityQuery}
                  onChange={(event) => {
                    const nextValue = event.target.value;
                    setCityQuery(nextValue);
                    setSelectedCity(null);
                    setActiveCityIndex(-1);
                    setCityOptions([]);
                    setSelectedWarehouse(null);
                    setWarehouseQuery("");
                    setWarehouseOptions([]);
                    setActiveWarehouseIndex(-1);
                    setSelectedStreet(null);
                    setStreetQuery("");
                    setStreetOptions([]);
                    setActiveStreetIndex(-1);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      setCityOptions([]);
                      setActiveCityIndex(-1);
                      return;
                    }
                    if (!cityOptions.length) {
                      return;
                    }
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setActiveCityIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, cityOptions.length - 1)));
                      return;
                    }
                    if (event.key === "ArrowUp") {
                      event.preventDefault();
                      setActiveCityIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                      return;
                    }
                    if (event.key === "Enter") {
                      event.preventDefault();
                      const resolvedIndex = activeCityIndex >= 0 ? activeCityIndex : 0;
                      const selected = cityOptions[resolvedIndex];
                      if (!selected) {
                        return;
                      }
                      applyCitySelection(selected);
                    }
                  }}
                  placeholder={t("placeholders.npCity")}
                  className="h-10 rounded-md border px-3"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                />
                {(cityLoading || cityOptions.length > 0) && cityQuery.trim().length >= CITY_LOOKUP_MIN_QUERY_LENGTH ? (
                  <div className="absolute left-0 right-0 top-[3.5rem] z-20 max-h-56 overflow-auto rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                    {cityLoading ? (
                      <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                        {t("lookup.loading")}
                      </div>
                    ) : cityOptions.length ? (
                      cityOptions.map((item, index) => {
                        const meta = [item.main_description, item.area, item.region]
                          .map((value) => String(value || "").trim())
                          .filter(Boolean)
                          .join(" • ");
                        return (
                          <button
                            key={item.ref}
                            type="button"
                            data-nav-scope="checkout-city"
                            data-nav-index={index}
                            className="flex min-h-10 w-full flex-col items-start justify-center gap-0.5 border-b px-3 py-1.5 text-left text-xs last:border-b-0"
                            style={{
                              borderColor: "var(--border)",
                              backgroundColor: index === activeCityIndex ? "var(--surface-2)" : "var(--surface)",
                            }}
                            onMouseEnter={() => setActiveCityIndex(index)}
                            onClick={() => applyCitySelection(item)}
                          >
                            <span className="w-full truncate font-medium">{item.label}</span>
                            {meta ? (
                              <span className="w-full truncate text-[11px]" style={{ color: "var(--muted)" }}>
                                {meta}
                              </span>
                            ) : null}
                          </button>
                        );
                      })
                    ) : (
                      <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                        {t("lookup.noResults")}
                      </div>
                    )}
                  </div>
                ) : null}
              </label>
            ) : null}

            {deliveryOption === "nova_poshta_warehouse" ? (
              <label ref={warehouseLookupRootRef} className="relative flex flex-col gap-1 text-xs">
                {t("fields.npDestination")}
                <input
                  value={warehouseQuery}
                  disabled={!selectedCity}
                  onChange={(event) => {
                    setWarehouseQuery(event.target.value);
                    setSelectedWarehouse(null);
                    setWarehouseOptions([]);
                    setActiveWarehouseIndex(-1);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      setWarehouseOptions([]);
                      setActiveWarehouseIndex(-1);
                      return;
                    }
                    if (!warehouseOptions.length) {
                      return;
                    }
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setActiveWarehouseIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, warehouseOptions.length - 1)));
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
                      const selected = warehouseOptions[resolvedIndex];
                      if (!selected) {
                        return;
                      }
                      applyWarehouseSelection(selected);
                    }
                  }}
                  placeholder={t("placeholders.npDestination")}
                  className="h-10 rounded-md border px-3 disabled:opacity-60"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                />
                {(warehouseLoading || warehouseOptions.length > 0) && selectedCity ? (
                  <div className="absolute left-0 right-0 top-[3.5rem] z-20 max-h-56 overflow-auto rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                    {warehouseLoading ? (
                      <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                        {t("lookup.loading")}
                      </div>
                    ) : warehouseOptions.length ? (
                      warehouseOptions.map((item, index) => {
                        const display = formatWarehouseLookupDisplay(item, npLocale);
                        return (
                          <button
                            key={item.ref}
                            type="button"
                            data-nav-scope="checkout-warehouse"
                            data-nav-index={index}
                            className="flex min-h-10 w-full flex-col items-start justify-center gap-0.5 border-b px-3 py-1.5 text-left text-xs last:border-b-0"
                            style={{
                              borderColor: "var(--border)",
                              backgroundColor: index === activeWarehouseIndex ? "var(--surface-2)" : "var(--surface)",
                            }}
                            onMouseEnter={() => setActiveWarehouseIndex(index)}
                            onClick={() => applyWarehouseSelection(item)}
                          >
                            <span className="w-full truncate font-medium">{display.label}</span>
                            {display.subtitle ? (
                              <span className="w-full truncate text-[11px]" style={{ color: "var(--muted)" }}>
                                {display.subtitle}
                              </span>
                            ) : null}
                          </button>
                        );
                      })
                    ) : (
                      <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                        {t("lookup.noResults")}
                      </div>
                    )}
                  </div>
                ) : null}
              </label>
            ) : null}

            {deliveryOption === "nova_poshta_courier" ? (
              <>
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,0.45fr)_minmax(0,0.6fr)]">
                  <label ref={streetLookupRootRef} className="relative flex flex-col gap-1 text-xs">
                    {t("fields.npStreet")}
                    <input
                      value={streetQuery}
                      disabled={!selectedCity}
                      onChange={(event) => {
                        setStreetQuery(event.target.value);
                        setSelectedStreet(null);
                        setStreetOptions([]);
                        setActiveStreetIndex(-1);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") {
                          setStreetOptions([]);
                          setActiveStreetIndex(-1);
                          return;
                        }
                        if (!streetOptions.length) {
                          return;
                        }
                        if (event.key === "ArrowDown") {
                          event.preventDefault();
                          setActiveStreetIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, streetOptions.length - 1)));
                          return;
                        }
                        if (event.key === "ArrowUp") {
                          event.preventDefault();
                          setActiveStreetIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                          return;
                        }
                        if (event.key === "Enter") {
                          event.preventDefault();
                          const resolvedIndex = activeStreetIndex >= 0 ? activeStreetIndex : 0;
                          const selected = streetOptions[resolvedIndex];
                          if (!selected) {
                            return;
                          }
                          applyStreetSelection(selected);
                        }
                      }}
                      placeholder={t("placeholders.npStreet")}
                      className="h-10 rounded-md border px-3 disabled:opacity-60"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    />
                    {(streetLoading || streetOptions.length > 0) && streetQuery.trim().length >= STREET_LOOKUP_MIN_QUERY_LENGTH && selectedCity ? (
                      <div className="absolute left-0 right-0 top-[3.5rem] z-20 max-h-56 overflow-auto rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                        {streetLoading ? (
                          <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                            {t("lookup.loading")}
                          </div>
                        ) : streetOptions.length ? (
                          streetOptions.map((item, index) => (
                            <button
                              key={item.street_ref}
                              type="button"
                              data-nav-scope="checkout-street"
                              data-nav-index={index}
                              className="flex h-10 w-full items-center border-b px-3 text-left text-xs last:border-b-0"
                              style={{
                                borderColor: "var(--border)",
                                backgroundColor: index === activeStreetIndex ? "var(--surface-2)" : "var(--surface)",
                              }}
                              onMouseEnter={() => setActiveStreetIndex(index)}
                              onClick={() => applyStreetSelection(item)}
                            >
                              {item.label}
                            </button>
                          ))
                        ) : (
                          <div className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>
                            {t("lookup.noResults")}
                          </div>
                        )}
                      </div>
                    ) : null}
                  </label>

                  <label className="flex flex-col gap-1 text-xs">
                    {t("fields.npHouse")}
                    <input
                      value={house}
                      onChange={(event) => setHouse(event.target.value)}
                      placeholder={t("placeholders.npHouse")}
                      required={deliveryOption === "nova_poshta_courier"}
                      className="h-10 rounded-md border px-3"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    />
                  </label>

                  <label className="flex flex-col gap-1 text-xs">
                    {t("fields.npApartment")}
                    <input
                      value={apartment}
                      onChange={(event) => setApartment(event.target.value)}
                      placeholder={t("placeholders.npApartment")}
                      className="h-10 rounded-md border px-3"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    />
                  </label>
                </div>
              </>
            ) : null}
          </div>

          <h2 className="mt-5 text-lg font-semibold">{t("sections.payment")}</h2>
          <div className="mt-3 grid gap-3">
            <PaymentMethodToggle
              value={paymentMethod}
              onChange={setPaymentMethod}
              labels={{
                monobankTitle: t("payment.monobank"),
                monobankHint: t("payment.monobankHint"),
                codTitle: t("payment.cashOnDelivery"),
                codHint: t("payment.cashOnDeliveryHint"),
                novapayTitle: t("payment.novapay"),
                novapayHint: t("payment.novapayHint"),
                liqpayTitle: t("payment.liqpay"),
                liqpayHint: t("payment.liqpayHint"),
              }}
            />

            <label className="flex flex-col gap-1 text-xs">
              {t("fields.comment")}
              <textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                rows={3}
                className="rounded-md border px-3 py-2"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
            </label>

            {monobankWidgetLoading ? (
              <p className="text-xs" style={{ color: "var(--muted)" }}>{t("payment.widgetLoading")}</p>
            ) : null}

            {monobankWidgetState && paymentMethod === "monobank" ? (
              <MonoPayWidget widget={monobankWidgetState.widget} pageUrl={monobankWidgetState.page_url} t={(key) => t(key)} />
            ) : null}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-4 inline-flex rounded-md border px-4 py-2 text-sm disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            {isSubmitting ? t("actions.submitting") : t("actions.submit")}
          </button>
        </form>

        <div className="space-y-3">
          <CartSummaryBlock
            itemsCount={preview?.items_count ?? cart.summary.items_count}
            subtotal={preview?.subtotal ?? cart.summary.subtotal}
            currency={cart.currency}
          />

          <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <h2 className="text-sm font-semibold">{t("sections.promo")}</h2>
            <div className="mt-2 grid gap-2">
              <div className="flex gap-2">
                <input
                  value={promoInput}
                  onChange={(event) => setPromoInput(event.target.value.toUpperCase())}
                  placeholder={t("promo.placeholder")}
                  className="h-9 min-w-0 flex-1 rounded-md border px-3 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                />
                <button
                  type="button"
                  disabled={isPromoApplying || !promoInput.trim()}
                  className="h-9 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  onClick={() => {
                    void handleApplyPromo();
                  }}
                >
                  {isPromoApplying ? t("promo.actions.applying") : t("promo.actions.apply")}
                </button>
                {appliedPromoCode ? (
                  <button
                    type="button"
                    disabled={isPromoApplying}
                    className="h-9 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    onClick={() => {
                      void handleClearPromo();
                    }}
                  >
                    {t("promo.actions.clear")}
                  </button>
                ) : null}
              </div>

              {preview?.promo ? (
                <div className="rounded-lg border p-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                  <p><span style={{ color: "var(--muted)" }}>{t("promo.labels.code")}:</span> <strong>{preview.promo.code}</strong></p>
                  <p className="mt-1">
                    <span style={{ color: "var(--muted)" }}>{t("promo.labels.type")}:</span>{" "}
                    {preview.promo.discount_type === "delivery_fee" ? t("promo.types.delivery") : t("promo.types.product")}
                  </p>
                  <p className="mt-1">
                    <span style={{ color: "var(--muted)" }}>{t("promo.labels.discount")}:</span>{" "}
                    {preview.promo.total_discount} {cart.currency}
                  </p>
                  {preview.promo.delivery_discount !== "0.00" ? (
                    <p className="mt-1">
                      <span style={{ color: "var(--muted)" }}>{t("promo.labels.deliverySavings")}:</span>{" "}
                      {preview.promo.delivery_discount} {cart.currency}
                    </p>
                  ) : null}
                  {preview.promo.product_discount !== "0.00" ? (
                    <p className="mt-1">
                      <span style={{ color: "var(--muted)" }}>{t("promo.labels.productSavings")}:</span>{" "}
                      {preview.promo.product_discount} {cart.currency}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <h2 className="text-sm font-semibold">{t("sections.orderReview")}</h2>
            <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
              {t("review.deliveryFee", { fee: preview?.delivery_fee ?? "0.00", currency: cart.currency })}
            </p>
            {(preview?.discount_total ?? "0.00") !== "0.00" ? (
              <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
                {t("review.discount", { amount: preview?.discount_total ?? "0.00", currency: cart.currency })}
              </p>
            ) : null}
            <p className="mt-1 text-sm font-semibold">
              {t("review.total", { total: preview?.total ?? cart.summary.subtotal, currency: cart.currency })}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
