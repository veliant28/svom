"use client";

import { useEffect, useRef, useState } from "react";
import Script from "next/script";
import { useLocale, useTranslations } from "next-intl";

import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { formatDateTime, formatMoney, resolveOrderStatusChipTone } from "@/features/account/lib/account-formatters";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { getCheckoutMonobankWidget } from "@/features/checkout/api/monobank-payment";
import { MonobankFallbackButton } from "@/features/checkout/components/payment/monobank-fallback-button";
import { MONOBANK_OFFICIAL_WIDGETS_ENABLED } from "@/features/checkout/lib/monobank-widget-flags";
import type { MonobankWidgetInit } from "@/features/checkout/types/payment";
import { getOrder } from "@/features/commerce/api/get-order";
import type { Order } from "@/features/commerce/types";
import { Link } from "@/i18n/navigation";
import { useTheme } from "@/shared/components/theme/theme-provider";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type MonoPayInitResult = {
  button?: HTMLElement;
};

type MonoPayApi = {
  init: (config: {
    keyId: string;
    signature: string;
    requestId: string;
    payloadBase64: string;
    ui?: {
      buttonType?: "pay";
      theme?: "dark" | "light";
      corners?: "rounded" | "square";
    };
    callbacks?: {
      onButtonReady?: () => void;
      onClick?: () => void;
      onInvoiceCreate?: (payload: unknown) => void;
      onSuccess?: (payload: unknown) => void;
      onError?: (error: unknown) => void;
    };
  }) => MonoPayInitResult;
};

function ValueField({
  label,
  value,
  bold = false,
}: {
  label: string;
  value: string;
  bold?: boolean;
}) {
  return (
    <div
      className="rounded-md border px-3 py-2"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
    >
      <p className="text-[11px]" style={{ color: "var(--muted)" }}>{label}</p>
      <p className={`mt-1 text-sm ${bold ? "font-semibold" : "font-medium"} text-[var(--text)]`}>{value || "-"}</p>
    </div>
  );
}

function resolveDeliveryMethodLabel(value: Order["delivery_method"], locale: string): string {
  const normalizedLocale = locale.toLowerCase();
  if (value === "pickup") {
    if (normalizedLocale.startsWith("uk")) {
      return "Самовивіз";
    }
    if (normalizedLocale.startsWith("en")) {
      return "Pickup";
    }
    return "Самовывоз";
  }
  if (value === "courier") {
    if (normalizedLocale.startsWith("uk")) {
      return "Курʼєр";
    }
    if (normalizedLocale.startsWith("en")) {
      return "Courier";
    }
    return "Курьер";
  }
  if (normalizedLocale.startsWith("en")) {
    return "Nova Poshta";
  }
  return "Новая Почта";
}

function resolvePaymentMethodLabel(value: Order["payment_method"], locale: string): string {
  const normalizedLocale = locale.toLowerCase();
  if (value === "cash_on_delivery") {
    if (normalizedLocale.startsWith("uk")) {
      return "Післяплата";
    }
    if (normalizedLocale.startsWith("en")) {
      return "Cash on delivery";
    }
    return "Наложенный платеж";
  }
  if (value === "monobank") {
    return "Monobank";
  }
  if (normalizedLocale.startsWith("uk")) {
    return "Оплата карткою";
  }
  if (normalizedLocale.startsWith("en")) {
    return "Card payment";
  }
  return "Оплата картой";
}

function MonopayInlineButton({
  token,
  orderId,
  pageUrl,
  theme,
}: {
  token: string | null;
  orderId: string;
  pageUrl: string;
  theme: "light" | "dark";
}) {
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [widgetPayload, setWidgetPayload] = useState<MonobankWidgetInit | null>(null);
  const [widgetReady, setWidgetReady] = useState(false);
  const [widgetFailed, setWidgetFailed] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fallbackTimerRef = useRef<number | null>(null);

  useEffect(() => {
    let isMounted = true;

    setWidgetPayload(null);
    setWidgetReady(false);
    setWidgetFailed(false);

    if (!MONOBANK_OFFICIAL_WIDGETS_ENABLED) {
      setWidgetFailed(true);
      return () => {
        isMounted = false;
      };
    }

    if (!token) {
      setWidgetFailed(true);
      return () => {
        isMounted = false;
      };
    }

    void (async () => {
      try {
        const response = await getCheckoutMonobankWidget(token, orderId);
        if (!isMounted) {
          return;
        }
        setWidgetPayload(response.widget);
        if (!response.widget) {
          setWidgetFailed(true);
        }
      } catch {
        if (isMounted) {
          setWidgetFailed(true);
        }
      }
    })();

    return () => {
      if (fallbackTimerRef.current) {
        window.clearTimeout(fallbackTimerRef.current);
        fallbackTimerRef.current = null;
      }
      isMounted = false;
    };
  }, [orderId, token]);

  useEffect(() => {
    if (!MONOBANK_OFFICIAL_WIDGETS_ENABLED) {
      return;
    }

    const monoPay = (window as Window & { MonoPay?: MonoPayApi }).MonoPay;
    if (!scriptLoaded || !widgetPayload || !containerRef.current || !monoPay) {
      return;
    }

    containerRef.current.innerHTML = "";
    setWidgetReady(false);

    try {
      const result = monoPay.init({
        keyId: widgetPayload.key_id,
        signature: widgetPayload.signature,
        requestId: widgetPayload.request_id,
        payloadBase64: widgetPayload.payload_base64,
        ui: {
          buttonType: "pay",
          theme: theme === "dark" ? "light" : "dark",
          corners: "rounded",
        },
        callbacks: {
          onClick: () => {
            if (fallbackTimerRef.current) {
              window.clearTimeout(fallbackTimerRef.current);
            }
            fallbackTimerRef.current = window.setTimeout(() => {
              window.location.assign(pageUrl);
            }, 1200);
          },
          onInvoiceCreate: () => {
            if (fallbackTimerRef.current) {
              window.clearTimeout(fallbackTimerRef.current);
              fallbackTimerRef.current = null;
            }
          },
          onError: () => {
            if (fallbackTimerRef.current) {
              window.clearTimeout(fallbackTimerRef.current);
              fallbackTimerRef.current = null;
            }
            window.location.assign(pageUrl);
          },
        },
      });

      if (!result?.button) {
        setWidgetFailed(true);
        return;
      }

      const scaledWrapper = document.createElement("div");
      scaledWrapper.style.display = "inline-block";
      scaledWrapper.style.zoom = "82%";
      scaledWrapper.style.transformOrigin = "right center";
      scaledWrapper.appendChild(result.button);
      containerRef.current.appendChild(scaledWrapper);
      setWidgetReady(true);
      setWidgetFailed(false);
    } catch {
      setWidgetFailed(true);
    }
  }, [pageUrl, scriptLoaded, theme, widgetPayload]);

  const shouldShowFallback = !widgetReady || widgetFailed;

  return (
    <div className="shrink-0">
      {MONOBANK_OFFICIAL_WIDGETS_ENABLED ? (
        <Script
          src="https://pay.monobank.ua/mono-pay-button/v1/mono-pay-button.js"
          strategy="afterInteractive"
          onLoad={() => {
            setScriptLoaded(true);
          }}
          onError={() => {
            setWidgetFailed(true);
          }}
        />
      ) : null}
      <div ref={containerRef} />
      {shouldShowFallback ? (
        <MonobankFallbackButton
          variant="pay"
          theme={theme}
          href={pageUrl}
          monoPayReady={MONOBANK_OFFICIAL_WIDGETS_ENABLED && scriptLoaded}
          className="shrink-0"
          ariaLabel="Pay with Monobank"
        />
      ) : null}
    </div>
  );
}

export function AccountOrderDetailPage({ orderId }: { orderId: string }) {
  const t = useTranslations("commerce.orders");
  const locale = useLocale();
  const { theme } = useTheme();
  const { token, isAuthenticated } = useAuth();
  const { showApiError } = useStorefrontFeedback();
  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadOrder() {
      if (!token || !isAuthenticated) {
        if (isMounted) {
          setOrder(null);
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      try {
        const response = await getOrder(token, orderId);
        if (isMounted) {
          setOrder(response);
        }
      } catch (fetchError) {
        if (isMounted) {
          setOrder(null);
        }
        showApiError(fetchError, t("states.error"));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadOrder();

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, orderId, showApiError, t, token]);

  if (!isAuthenticated) {
    return <AccountAuthRequired title={t("title")} message={t("authRequired")} loginLabel={t("goToLogin")} />;
  }

  if (isLoading) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          {t("states.loading")}
        </p>
      </section>
    );
  }

  if (!order) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          {t("states.error")}
        </p>
      </section>
    );
  }

  const statusLabel = t(`status.${order.status}`);
  const statusTone = resolveOrderStatusChipTone(order.status);
  const paymentLabel = resolvePaymentMethodLabel(order.payment_method, locale);
  const monobankPageUrl = order.payment_method === "monobank" ? (order.payment?.page_url || "").trim() : "";

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <Link href="/account/orders" className="text-sm" style={{ color: "var(--muted)" }}>
        ← {t("title")}
      </Link>

      <article
        className="mt-3 rounded-xl border p-4"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold">{order.order_number}</h1>
            <p className="text-xs" style={{ color: "var(--muted)" }}>
              {formatDateTime(order.placed_at, locale)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <p className="text-base font-semibold">{formatMoney(order.total, order.currency, locale)}</p>
            <BackofficeStatusChip tone={statusTone}>{statusLabel}</BackofficeStatusChip>
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <section className="rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <p className="text-sm font-semibold">Клиент</p>
            <div className="mt-3 grid gap-2">
              <ValueField label="Email" value={order.contact_email || "-"} />
              <ValueField label="ФИО" value={order.contact_full_name || "-"} />
              <ValueField label="Телефон" value={order.contact_phone || "-"} />
              <ValueField label="Позиций" value={String(order.items.length)} bold />
            </div>
          </section>

          <section className="rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <p className="text-sm font-semibold">Доставка и оплата</p>
            <div className="mt-3 grid gap-2">
              <ValueField label="Способ доставки" value={resolveDeliveryMethodLabel(order.delivery_method, locale)} />
              <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px]" style={{ color: "var(--muted)" }}>Способ оплаты</p>
                    <p className="mt-1 text-sm font-medium text-[var(--text)]">{paymentLabel || "-"}</p>
                  </div>
                  {monobankPageUrl ? (
                    <MonopayInlineButton token={token} orderId={order.id} pageUrl={monobankPageUrl} theme={theme} />
                  ) : null}
                </div>
              </div>
              <ValueField label="Город доставки" value={order.delivery_city_label || "-"} />
              <ValueField label="Отделение / почтомат / адрес" value={order.delivery_destination_label || "-"} />
            </div>
          </section>
        </div>

        {order.items.length > 0 ? (
          <section className="mt-3 rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <p className="text-sm font-semibold">{t("subtitle")}</p>
            <div className="mt-3 overflow-x-auto rounded-md border" style={{ borderColor: "var(--border)" }}>
              <table className="min-w-full border-separate border-spacing-0 text-xs">
                <thead style={{ backgroundColor: "var(--surface-2)", color: "var(--muted)" }}>
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">{t("table.sku")}</th>
                    <th className="px-3 py-2 text-left font-medium">{t("table.product")}</th>
                    <th className="px-3 py-2 text-right font-medium">{t("table.qty")}</th>
                    <th className="px-3 py-2 text-right font-medium">{t("table.total")}</th>
                  </tr>
                </thead>
                <tbody>
                  {order.items.map((item) => (
                    <tr key={item.id} style={{ borderTop: "1px solid var(--border)" }}>
                      <td className="px-3 py-2">{item.product_sku || "-"}</td>
                      <td className="px-3 py-2">{item.product_name}</td>
                      <td className="px-3 py-2 text-right">{item.quantity}</td>
                      <td className="px-3 py-2 text-right">{formatMoney(item.line_total, order.currency, locale)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}
      </article>
    </section>
  );
}
