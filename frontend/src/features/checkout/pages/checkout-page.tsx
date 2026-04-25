"use client";

import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
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
import { CheckoutContactSection } from "@/features/checkout/components/checkout-contact-section";
import { CheckoutDeliverySection } from "@/features/checkout/components/checkout-delivery-section";
import { CheckoutPaymentSection } from "@/features/checkout/components/checkout-payment-section";
import { CheckoutSidebar } from "@/features/checkout/components/checkout-sidebar";
import { CheckoutStateMessage } from "@/features/checkout/components/checkout-state-message";
import {
  CITY_LOOKUP_MIN_QUERY_LENGTH,
  STREET_LOOKUP_MIN_QUERY_LENGTH,
  formatWarehouseInputValue,
  resolveCheckoutDeliveryAddress,
  resolveCheckoutDeliverySnapshot,
  resolveEffectiveDeliveryMethod,
  resolveNpLocale,
  resolvePromoErrorKey,
  scrollDropdownOptionIntoView,
  type CheckoutDeliveryOption,
} from "@/features/checkout/lib/checkout-page.helpers";
import type { CheckoutPaymentMethod, MonobankWidgetResponse } from "@/features/checkout/types/payment";
import type { CheckoutPreview } from "@/features/commerce/types";
import { isApiRequestError } from "@/shared/api/http-client";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";
import {
  formatPhoneInput,
  isPhoneInputValid,
} from "@/shared/lib/phone-input";

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
    return resolveNpLocale(locale);
  }, [locale]);

  const effectiveDeliveryMethod = useMemo(() => resolveEffectiveDeliveryMethod(deliveryOption), [deliveryOption]);

  const resolvedDeliveryAddress = useMemo(() => {
    return resolveCheckoutDeliveryAddress({
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
    });
  }, [apartment, cityQuery, deliveryOption, house, npLocale, selectedCity, selectedStreet, selectedWarehouse, streetQuery, warehouseQuery]);

  const resolvedDeliverySnapshot = useMemo<Record<string, unknown>>(() => {
    return resolveCheckoutDeliverySnapshot({
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
    });
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

  function handlePromoInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    if (isPromoApplying || !promoInput.trim()) {
      return;
    }
    void handleApplyPromo();
  }

  if (!isAuthenticated) {
    return <CheckoutStateMessage t={t} messageKey="authRequired" actionHref="/login" actionKey="goToLogin" />;
  }

  if (!cart || cart.items.length === 0) {
    return <CheckoutStateMessage t={t} messageKey="emptyCart" actionHref="/catalog" actionKey="goToCatalog" />;
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
          <CheckoutContactSection
            lastName={lastName}
            firstName={firstName}
            middleName={middleName}
            phone={phone}
            t={t}
            setLastName={setLastName}
            setFirstName={setFirstName}
            setMiddleName={setMiddleName}
            setPhone={setPhone}
            setIsLastNameDirty={setIsLastNameDirty}
            setIsFirstNameDirty={setIsFirstNameDirty}
            setIsMiddleNameDirty={setIsMiddleNameDirty}
            setIsPhoneDirty={setIsPhoneDirty}
          />

          <CheckoutDeliverySection
            deliveryOption={deliveryOption}
            npDestinationLine1={npDestinationLine1}
            npDestinationLine2={npDestinationLine2}
            cityLookupRootRef={cityLookupRootRef}
            warehouseLookupRootRef={warehouseLookupRootRef}
            streetLookupRootRef={streetLookupRootRef}
            cityQuery={cityQuery}
            cityOptions={cityOptions}
            cityLoading={cityLoading}
            activeCityIndex={activeCityIndex}
            selectedCity={selectedCity}
            warehouseQuery={warehouseQuery}
            warehouseOptions={warehouseOptions}
            warehouseLoading={warehouseLoading}
            activeWarehouseIndex={activeWarehouseIndex}
            streetQuery={streetQuery}
            streetOptions={streetOptions}
            streetLoading={streetLoading}
            activeStreetIndex={activeStreetIndex}
            house={house}
            apartment={apartment}
            npLocale={npLocale}
            t={t}
            setDeliveryOption={setDeliveryOption}
            setCityQuery={setCityQuery}
            setCityOptions={setCityOptions}
            setActiveCityIndex={setActiveCityIndex}
            setSelectedCity={setSelectedCity}
            setWarehouseQuery={setWarehouseQuery}
            setWarehouseOptions={setWarehouseOptions}
            setActiveWarehouseIndex={setActiveWarehouseIndex}
            setSelectedWarehouse={setSelectedWarehouse}
            setStreetQuery={setStreetQuery}
            setStreetOptions={setStreetOptions}
            setActiveStreetIndex={setActiveStreetIndex}
            setSelectedStreet={setSelectedStreet}
            setHouse={setHouse}
            setApartment={setApartment}
            onCitySelect={applyCitySelection}
            onWarehouseSelect={applyWarehouseSelection}
            onStreetSelect={applyStreetSelection}
          />

          <CheckoutPaymentSection
            paymentMethod={paymentMethod}
            comment={comment}
            monobankWidgetLoading={monobankWidgetLoading}
            monobankWidgetState={monobankWidgetState}
            t={t}
            setPaymentMethod={setPaymentMethod}
            setComment={setComment}
          />

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-4 inline-flex rounded-md border px-4 py-2 text-sm disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            {isSubmitting ? t("actions.submitting") : t("actions.submit")}
          </button>
        </form>

        <CheckoutSidebar
          cart={cart}
          preview={preview}
          promoInput={promoInput}
          appliedPromoCode={appliedPromoCode}
          isPromoApplying={isPromoApplying}
          t={t}
          onPromoInputChange={setPromoInput}
          onPromoInputKeyDown={handlePromoInputKeyDown}
          onApplyPromo={() => { void handleApplyPromo(); }}
          onClearPromo={() => { void handleClearPromo(); }}
        />
      </div>
    </section>
  );
}
