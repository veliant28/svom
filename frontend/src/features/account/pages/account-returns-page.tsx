"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { AccountReturnsList } from "@/features/account/components/returns/account-returns-list";
import { getReturnRequests } from "@/features/commerce/api/returns-api";
import { useCommerceSocket } from "@/features/commerce/hooks/use-commerce-socket";
import type { CommerceRealtimeEvent, ReturnRequestListItem } from "@/features/commerce/types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { Link, useRouter } from "@/i18n/navigation";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

const RETURNS_POLL_INTERVAL_MS = 15000;

export function AccountReturnsPage() {
  const t = useTranslations("commerce.returns");
  const { token, user, isAuthenticated } = useAuth();
  const { showApiError } = useStorefrontFeedback();
  const router = useRouter();

  const [items, setItems] = useState<ReturnRequestListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const commerceSocket = useCommerceSocket({
    token,
    path: "/ws/commerce/user/",
    enabled: isAuthenticated,
    onEvent: (event: CommerceRealtimeEvent) => {
      if (event.type !== "commerce.return.updated") {
        return;
      }
      setItems((current) =>
        current.map((row) => (
          row.id === event.payload.return_id
            ? {
              ...row,
              status: event.payload.status,
              tracking_number: event.payload.tracking_number,
            }
            : row
        )),
      );
    },
  });

  useEffect(() => {
    if (!isAuthenticated || !user) {
      return;
    }
    if (!user.returns_enabled) {
      router.replace("/account/orders");
    }
  }, [isAuthenticated, router, user]);

  useEffect(() => {
    let mounted = true;

    async function load() {
      if (!token || !isAuthenticated || !user?.returns_enabled) {
        if (mounted) {
          setItems([]);
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      try {
        const data = await getReturnRequests(token);
        if (mounted) {
          setItems(data);
        }
      } catch (error) {
        if (mounted) {
          setItems([]);
        }
        showApiError(error, t("states.error"));
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    void load();
    return () => {
      mounted = false;
    };
  }, [isAuthenticated, showApiError, t, token, user?.returns_enabled]);

  useEffect(() => {
    if (!token || !isAuthenticated || !user?.returns_enabled) {
      return;
    }
    if (commerceSocket.isConnected) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void getReturnRequests(token)
        .then((data) => {
          setItems(data);
        })
        .catch(() => {
          // Silent background refresh. UI keeps last known values.
        });
    }, RETURNS_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [commerceSocket.isConnected, isAuthenticated, token, user?.returns_enabled]);

  if (!isAuthenticated) {
    return <AccountAuthRequired title={t("title")} message={t("authRequired")} loginLabel={t("goToLogin")} />;
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>{t("subtitle")}</p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/account/returns/create"
            className="inline-flex h-10 items-center rounded-md border px-4 text-sm font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            title={t("createHint")}
          >
            {t("actions.create")}
          </Link>
        </div>
      </div>

      <div className="mt-4">
        <AccountReturnsList items={items} isLoading={isLoading} />
      </div>
    </section>
  );
}
