"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { AccountOrdersList } from "@/features/account/components/orders/account-orders-list";
import { getOrders } from "@/features/commerce/api/get-orders";
import type { Order } from "@/features/commerce/types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function AccountOrdersPage() {
  const t = useTranslations("commerce.orders");
  const { token, isAuthenticated } = useAuth();
  const { showApiError } = useStorefrontFeedback();
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);

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
