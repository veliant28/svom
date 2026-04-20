"use client";

import { useEffect, useRef, useState } from "react";
import Script from "next/script";

import { MonobankFallbackButton } from "@/features/checkout/components/payment/monobank-fallback-button";
import { getCheckoutMonobankSelectorWidget } from "@/features/checkout/api/monobank-payment";
import { MONOBANK_OFFICIAL_WIDGETS_ENABLED } from "@/features/checkout/lib/monobank-widget-flags";
import type { MonobankWidgetInit } from "@/features/checkout/types/payment";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useTheme } from "@/shared/components/theme/theme-provider";

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
      theme?: "dark" | "light";
      corners?: "rounded" | "square";
    };
    callbacks?: {
      onSuccess?: (payload: unknown) => void;
      onError?: (error: unknown) => void;
    };
  }) => MonoPayInitResult;
};

export function MonobankPaymentCard({
  title,
  selected,
  onSelect,
}: {
  title: string;
  hint: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const { token } = useAuth();
  const { theme } = useTheme();
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [widgetPayload, setWidgetPayload] = useState<MonobankWidgetInit | null>(null);
  const [widgetReady, setWidgetReady] = useState(false);
  const [widgetFailed, setWidgetFailed] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

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
        const response = await getCheckoutMonobankSelectorWidget(token);
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
      isMounted = false;
    };
  }, [token]);

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
          theme: theme === "dark" ? "light" : "dark",
          corners: "rounded",
        },
      });

      if (!result?.button) {
        setWidgetFailed(true);
        return;
      }

      result.button.style.pointerEvents = "none";

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
  }, [scriptLoaded, theme, widgetPayload]);

  const showFallback = !widgetReady || widgetFailed;

  return (
    <div className="relative">
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

      <div
        className="relative inline-flex h-11 w-full items-center justify-center overflow-hidden rounded-md border transition"
        style={{
          borderColor: selected ? "var(--accent)" : "var(--border)",
          backgroundColor: "var(--surface-2)",
          boxShadow: selected ? "0 0 0 2px var(--accent)" : "none",
        }}
      >
        <div ref={containerRef} className="pointer-events-none" />
        {showFallback ? (
          <MonobankFallbackButton
            variant="selector"
            theme={theme}
            monoPayReady={MONOBANK_OFFICIAL_WIDGETS_ENABLED && scriptLoaded}
            className="pointer-events-none absolute inset-0"
          />
        ) : null}
        <button
          type="button"
          className="absolute inset-0 z-10"
          onClick={onSelect}
          aria-pressed={selected}
          aria-label={title}
        />
      </div>
    </div>
  );
}
