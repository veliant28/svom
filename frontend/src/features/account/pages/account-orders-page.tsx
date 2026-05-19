"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { AccountOrdersList } from "@/features/account/components/orders/account-orders-list";
import { getOrders } from "@/features/commerce/api/get-orders";
import { useCommerceSocket } from "@/features/commerce/hooks/use-commerce-socket";
import type { CommerceRealtimeEvent, Order } from "@/features/commerce/types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

const ORDERS_POLL_INTERVAL_MS = 15000;

export function AccountOrdersPage() {
  const t = useTranslations("commerce.orders");
  const { token, isAuthenticated } = useAuth();
  const { showApiError } = useStorefrontFeedback();
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const commerceSocket = useCommerceSocket({
    token,
    path: "/ws/commerce/user/",
    enabled: isAuthenticated,
    onEvent: (event: CommerceRealtimeEvent) => {
      if (event.type !== "commerce.order.updated") {
        return;
      }
      setOrders((current) =>
        current.map((row) => (
          row.id === event.payload.order_id
            ? { ...row, status: event.payload.status }
            : row
        )),
      );
    },
  });

  useEffect(() => {
    let isMounted = true;

    async function loadOrders() {
      if (!token || !isAuthenticated) {
        if (isMounted) {
          setOrders([]);
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      try {
        const response = await getOrders(token);
        if (isMounted) {
          setOrders(response);
        }
      } catch (fetchError) {
        if (isMounted) {
          setOrders([]);
        }
        showApiError(fetchError, t("states.error"));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadOrders();

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, showApiError, t, token]);

  useEffect(() => {
    if (!token || !isAuthenticated) {
      return;
    }
    if (commerceSocket.isConnected) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void getOrders(token)
        .then((response) => {
          setOrders(response);
        })
        .catch(() => {
          // Silent background refresh. Keep current snapshot.
        });
    }, ORDERS_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [commerceSocket.isConnected, isAuthenticated, token]);

  if (!isAuthenticated) {
    return <AccountAuthRequired title={t("title")} message={t("authRequired")} loginLabel={t("goToLogin")} />;
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {t("subtitle")}
      </p>
      <div className="mt-4">
        <AccountOrdersList orders={orders} isLoading={isLoading} />
      </div>
    </section>
  );
}
