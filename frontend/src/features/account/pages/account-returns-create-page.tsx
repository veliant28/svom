"use client";

import { ArrowLeft, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { formatDateTime, formatMoney, resolveOrderStatusChipIcon, resolveOrderStatusChipTone } from "@/features/account/lib/account-formatters";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { getEligibleReturnOrders } from "@/features/commerce/api/returns-api";
import type { EligibleReturnOrder } from "@/features/commerce/types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { Link, useRouter } from "@/i18n/navigation";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function AccountReturnsCreatePage() {
  const t = useTranslations("commerce.returns");
  const tOrders = useTranslations("commerce.orders");
  const locale = useLocale();
  const { token, user, isAuthenticated } = useAuth();
  const { showApiError } = useStorefrontFeedback();
  const router = useRouter();

  const [isPolicyOpen, setIsPolicyOpen] = useState(true);
  const [orders, setOrders] = useState<EligibleReturnOrder[]>([]);
  const [isLoading, setIsLoading] = useState(true);

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
          setOrders([]);
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      try {
        const data = await getEligibleReturnOrders(token);
        if (mounted) {
          setOrders(data);
        }
      } catch (error) {
        if (mounted) {
          setOrders([]);
        }
        showApiError(error, t("states.eligibleLoadFailed"));
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

  if (!isAuthenticated) {
    return <AccountAuthRequired title={t("title")} message={t("authRequired")} loginLabel={t("goToLogin")} />;
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      {isPolicyOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
          <button type="button" className="absolute inset-0 bg-black/40" onClick={() => setIsPolicyOpen(false)} aria-label={t("actions.closePolicy")} />
          <article className="relative z-10 w-full max-w-xl rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <div className="mb-2 flex items-start justify-between gap-3">
              <h2 className="text-base font-semibold">{t("policy.title")}</h2>
              <button
                type="button"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                onClick={() => setIsPolicyOpen(false)}
                aria-label={t("actions.closePolicy")}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <ul className="space-y-1 text-sm" style={{ color: "var(--muted)" }}>
              <li>{t("policy.items.window")}</li>
              <li>{t("policy.items.condition")}</li>
              <li>{t("policy.items.nonReturnable")}</li>
              <li>{t("policy.items.shipping")}</li>
              <li>{t("policy.items.tracking")}</li>
              <li>{t("policy.items.refund")}</li>
            </ul>
          </article>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{t("createTitle")}</h1>
          <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>{t("createSubtitle")}</p>
        </div>
        <Link
          href="/account/returns"
          className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium transition hover:opacity-80"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--accent)" }}
        >
          <ArrowLeft size={14} />
          <span>{t("actions.backToReturns").replace("← ", "")}</span>
        </Link>
      </div>

      <div className="mt-4 space-y-3">
        {isLoading ? <p className="text-sm" style={{ color: "var(--muted)" }}>{t("states.loading")}</p> : null}

        {!isLoading && !orders.length ? (
          <p className="text-sm" style={{ color: "var(--muted)" }}>{t("states.noEligible")}</p>
        ) : null}

        {orders.map((order) => {
          const statusTone = resolveOrderStatusChipTone(order.status);
          const statusIcon = resolveOrderStatusChipIcon(order.status);
          const statusLabel = tOrders(`status.${order.status}`);

          return (
            <Link
              key={order.id}
              href={`/account/returns/create/${order.id}`}
              className="block rounded-xl border p-4 transition hover:opacity-95"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <article className="grid gap-3 sm:grid-cols-[minmax(12rem,1fr)_7.25rem_7.25rem_9.5rem_8.5rem] sm:items-center">
                <div className="min-w-0">
                  <p className="truncate text-base font-semibold">{order.order_number}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {formatDateTime(order.placed_at, locale)}
                  </p>
                </div>
                <p className="text-sm leading-[1.05]" style={{ color: "var(--muted)" }}>
                  {order.return_day_label}
                </p>
                <p className="text-sm leading-[1.05]" style={{ color: "var(--muted)" }}>
                  {tOrders("labels.items", { count: order.items_count })}
                </p>
                <p className="text-base font-semibold leading-[1.05]">{formatMoney(order.total, order.currency, locale)}</p>
                <div className="sm:justify-self-start">
                  <StatusChip tone={statusTone} icon={statusIcon} className="whitespace-nowrap">{statusLabel}</StatusChip>
                </div>
              </article>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
