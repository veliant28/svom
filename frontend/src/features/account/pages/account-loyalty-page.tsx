"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Clock3, Copy, MinusCircle, type LucideIcon, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { getMyLoyaltyCodes } from "@/features/commerce/api/get-my-loyalty-codes";
import type { LoyaltyPromoCode } from "@/features/commerce/types";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

function resolveStateChip(state: LoyaltyPromoCode["state"]): { tone: BackofficeStatusChipTone; icon: LucideIcon } {
  if (state === "active") {
    return { tone: "success", icon: CheckCircle2 };
  }
  if (state === "used") {
    return { tone: "blue", icon: Clock3 };
  }
  if (state === "expired") {
    return { tone: "error", icon: XCircle };
  }
  return { tone: "gray", icon: MinusCircle };
}

export function AccountLoyaltyPage() {
  const t = useTranslations("commerce.loyalty");
  const { token, isAuthenticated } = useAuth();
  const { showApiError, showSuccess } = useStorefrontFeedback();
  const [codes, setCodes] = useState<LoyaltyPromoCode[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function loadCodes() {
      if (!token || !isAuthenticated) {
        if (mounted) {
          setCodes([]);
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      try {
        const response = await getMyLoyaltyCodes(token);
        if (mounted) {
          setCodes(response);
        }
      } catch (error) {
        if (mounted) {
          setCodes([]);
        }
        showApiError(error, t("states.error"));
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    void loadCodes();

    return () => {
      mounted = false;
    };
  }, [isAuthenticated, showApiError, t, token]);

  if (!isAuthenticated) {
    return <AccountAuthRequired title={t("title")} message={t("authRequired")} loginLabel={t("goToLogin")} />;
  }

  async function copyPromoCode(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      showSuccess(t("messages.copied"));
    } catch {
      // Clipboard can be unavailable in some contexts.
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>{t("subtitle")}</p>

      {isLoading ? (
        <p className="mt-4 text-sm" style={{ color: "var(--muted)" }}>{t("states.loading")}</p>
      ) : null}

      {!isLoading && !codes.length ? (
        <div className="mt-4 rounded-xl border p-5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <p className="text-sm font-semibold">{t("states.emptyTitle")}</p>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>{t("states.emptyDescription")}</p>
        </div>
      ) : null}

      {!!codes.length ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {codes.map((promo) => {
            const stateChip = resolveStateChip(promo.state);
            return (
              <article
                key={promo.id}
                className="rounded-xl border p-4"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>{t("labels.code")}</p>
                    <p className="text-lg font-semibold tracking-[0.06em]">{promo.code}</p>
                  </div>
                  <BackofficeStatusChip tone={stateChip.tone} icon={stateChip.icon}>
                    {t(`states.values.${promo.state}`)}
                  </BackofficeStatusChip>
                </div>

                <div className="mt-3 grid grid-cols-[minmax(0,1fr)_auto] gap-2 text-sm">
                  <div className="grid gap-1">
                    <p>{t("labels.type")}: {promo.discount_type === "delivery_fee" ? t("types.delivery") : t("types.product")}</p>
                    <p>{t("labels.discount")}: {promo.discount_percent}%</p>
                    <p>{t("labels.usage")}: {promo.usage_count}/{promo.usage_limit}</p>
                    <p>{t("labels.expiresAt")}: {promo.expires_at ? new Date(promo.expires_at).toLocaleString() : t("labels.noExpiry")}</p>
                    {promo.reason ? <p className="min-w-0">{t("labels.reason")}: {promo.reason}</p> : null}
                  </div>
                  <div className="flex items-end">
                    <button
                      type="button"
                      className="inline-flex h-8 shrink-0 items-center gap-1 rounded-md border px-3 text-xs font-semibold"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        void copyPromoCode(promo.code);
                      }}
                    >
                      <Copy size={14} />
                      {t("actions.copy")}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
