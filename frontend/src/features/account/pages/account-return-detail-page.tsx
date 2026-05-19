"use client";

import { ArrowLeft, Check, LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { formatMoney } from "@/features/account/lib/account-formatters";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { ReturnStatusChip } from "@/features/backoffice/components/widgets/return-status-chip";
import { formatReturnDate, formatReturnMoney, formatTrackingNumber, normalizeTrackingDigits } from "@/features/account/lib/returns-formatters";
import { getReturnRequestDetail, submitReturnTrackingNumber } from "@/features/commerce/api/returns-api";
import { useCommerceSocket } from "@/features/commerce/hooks/use-commerce-socket";
import type { CommerceRealtimeEvent, ReturnRequestDetail } from "@/features/commerce/types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { Link, useRouter } from "@/i18n/navigation";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

const SHIPPING_DATA_VISIBLE_STATUSES = new Set([
  "approved",
  "awaiting_ttn",
  "in_transit",
  "received",
  "accepted",
  "refunded",
]);
const RETURNS_DETAIL_POLL_INTERVAL_MS = 15000;

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

function formatUaPhoneForDisplay(value: string): string {
  const raw = String(value || "").trim();
  if (!raw) {
    return "-";
  }
  const digits = raw.replace(/\D+/g, "");
  let normalized = "";
  if (digits.startsWith("380")) {
    normalized = digits;
  } else if (digits.startsWith("80")) {
    normalized = `3${digits}`;
  } else if (digits.startsWith("0")) {
    normalized = `38${digits}`;
  } else {
    normalized = `380${digits}`;
  }
  normalized = normalized.slice(0, 12);
  if (!/^380\d{9}$/.test(normalized)) {
    return raw;
  }
  const local = normalized.slice(2);
  const p1 = local.slice(0, 3);
  const p2 = local.slice(3, 6);
  const p3 = local.slice(6, 8);
  const p4 = local.slice(8, 10);
  return `+38 (${p1}) ${p2}-${p3}-${p4}`;
}

export function AccountReturnDetailPage({ returnId }: { returnId: string }) {
  const t = useTranslations("commerce.returns");
  const locale = useLocale();
  const { token, user, isAuthenticated } = useAuth();
  const { showApiError, showError, showInfo, showSuccess } = useStorefrontFeedback();
  const router = useRouter();
  const partialApprovalToastShownRef = useRef<Set<string>>(new Set());
  const adminCommentToastShownRef = useRef<Set<string>>(new Set());

  const [data, setData] = useState<ReturnRequestDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [trackingInput, setTrackingInput] = useState("");
  const [isSavingTracking, setIsSavingTracking] = useState(false);
  const commerceSocket = useCommerceSocket({
    token,
    path: "/ws/commerce/user/",
    enabled: isAuthenticated,
    onEvent: (event: CommerceRealtimeEvent) => {
      if (event.type !== "commerce.return.updated") {
        return;
      }
      setData((current) => {
        if (!current || current.id !== event.payload.return_id) {
          return current;
        }
        return {
          ...current,
          status: event.payload.status,
          tracking_number: event.payload.tracking_number,
          admin_comment: event.payload.admin_comment,
        };
      });
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
          setData(null);
          setIsLoading(false);
        }
        return;
      }

      setIsLoading(true);
      try {
        const payload = await getReturnRequestDetail(token, returnId);
        if (!mounted) {
          return;
        }
        setData(payload);
        setTrackingInput(formatTrackingNumber(payload.tracking_number));
      } catch (error) {
        if (mounted) {
          setData(null);
        }
        showApiError(error, t("states.detailLoadFailed"));
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
  }, [isAuthenticated, returnId, showApiError, t, token, user?.returns_enabled]);

  useEffect(() => {
    if (!data) {
      return;
    }
    if (partialApprovalToastShownRef.current.has(data.id)) {
      return;
    }
    const notApprovedCount = data.items.filter((item) => item.quantity_requested > 0 && item.quantity_approved <= 0).length;
    if (notApprovedCount <= 0) {
      return;
    }
    partialApprovalToastShownRef.current.add(data.id);
    const comment = String(data.admin_comment || "").trim();
    if (comment) {
      adminCommentToastShownRef.current.add(`${data.id}:${comment}`);
    }
    showInfo(
      comment
        ? t("toasts.notApprovedWithComment", { count: notApprovedCount, comment })
        : t("toasts.notApproved", { count: notApprovedCount }),
    );
  }, [data, showInfo, t]);

  useEffect(() => {
    if (!data) {
      return;
    }
    const comment = String(data.admin_comment || "").trim();
    if (!comment || !SHIPPING_DATA_VISIBLE_STATUSES.has(data.status)) {
      return;
    }
    const key = `${data.id}:${comment}`;
    if (adminCommentToastShownRef.current.has(key)) {
      return;
    }
    adminCommentToastShownRef.current.add(key);
    showInfo(t("toasts.adminComment", { comment }));
  }, [data, showInfo, t]);

  useEffect(() => {
    if (!token || !isAuthenticated || !user?.returns_enabled) {
      return;
    }
    if (commerceSocket.isConnected) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void getReturnRequestDetail(token, returnId)
        .then((payload) => {
          setData((current) => {
            if (!current) {
              return payload;
            }
            return payload;
          });
        })
        .catch(() => {
          // Silent background refresh. UI keeps last known values.
        });
    }, RETURNS_DETAIL_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [commerceSocket.isConnected, isAuthenticated, returnId, token, user?.returns_enabled]);

  const canEditTracking = useMemo(() => {
    if (!data) {
      return false;
    }
    return Boolean(data.can_edit_tracking_number);
  }, [data]);
  const showShippingData = useMemo(() => {
    if (!data) {
      return false;
    }
    return SHIPPING_DATA_VISIBLE_STATUSES.has(data.status);
  }, [data]);

  const trackingDigits = normalizeTrackingDigits(trackingInput);

  const serverTrackingNumber = data?.tracking_number || "";

  useEffect(() => {
    const normalizedCurrent = normalizeTrackingDigits(trackingInput);
    const normalizedServer = normalizeTrackingDigits(serverTrackingNumber);
    if (normalizedCurrent === normalizedServer) {
      return;
    }
    setTrackingInput(formatTrackingNumber(serverTrackingNumber));
  }, [serverTrackingNumber, trackingInput]);

  async function handleSaveTracking() {
    if (!token || !data || isSavingTracking) {
      return;
    }
    if (trackingDigits.length !== 14) {
      showError(t("toasts.invalidTtn"));
      return;
    }

    setIsSavingTracking(true);
    try {
      const payload = await submitReturnTrackingNumber(token, data.id, { tracking_number: trackingDigits });
      setData({
        ...data,
        status: payload.status as ReturnRequestDetail["status"],
        tracking_number: payload.tracking_number,
        customer_return_tracking_submitted_at: payload.customer_return_tracking_submitted_at,
        can_edit_tracking_number: true,
      });
      setTrackingInput(payload.tracking_number);
      showSuccess(t("toasts.ttnSaved"));
    } catch (error) {
      showApiError(error, t("toasts.ttnSaveFailed"));
    } finally {
      setIsSavingTracking(false);
    }
  }

  if (!isAuthenticated) {
    return <AccountAuthRequired title={t("title")} message={t("authRequired")} loginLabel={t("goToLogin")} />;
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <Link
        href="/account/returns"
        className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium transition hover:opacity-80"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--accent)" }}
      >
        <ArrowLeft size={14} />
        <span>{t("actions.backToReturns").replace("← ", "")}</span>
      </Link>

      {isLoading ? <p className="mt-4 text-sm" style={{ color: "var(--muted)" }}>{t("states.loading")}</p> : null}

      {!isLoading && data ? (
        <article className="mt-3 rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="truncate text-base font-semibold">
                {data.return_number}
                <span className="ml-2 text-xs font-normal" style={{ color: "var(--muted)" }}>
                  {formatReturnDate(data.created_at, locale)}
                </span>
              </p>
              <p className="text-xs" style={{ color: "var(--muted)" }}>{data.order_number}</p>
            </div>
            <div className="flex items-center gap-2">
              <p className="text-base font-semibold">{formatMoney(data.refund_amount, "UAH", locale)}</p>
              <ReturnStatusChip status={data.status} className="whitespace-nowrap" />
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <section className="rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="text-sm font-semibold">{t("fields.recipient")}</p>
              <div className="mt-3 grid gap-2">
                {showShippingData ? (
                  <>
                    <ValueField label={t("fields.recipient")} value={data.shipping_address.recipient_full_name || "-"} />
                    <ValueField label={t("fields.phone")} value={formatUaPhoneForDisplay(data.shipping_address.recipient_phone || "")} />
                    {canEditTracking ? (
                      <div
                        className="rounded-md border px-3 py-2"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold">{t("labels.trackingNumber")}</p>
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={formatTrackingNumber(trackingInput)}
                              onChange={(event) => setTrackingInput(formatTrackingNumber(event.target.value))}
                              placeholder="59 XXXX XXXX XXXX"
                              className="h-10 w-[240px] rounded-md border px-3 text-sm"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                            />
                            <BackofficeTooltip content={t("actions.saveTracking")} placement="top" align="center" wrapperClassName="inline-flex shrink-0">
                              <button
                                type="button"
                                className="inline-flex h-10 w-10 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-60"
                                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                                onClick={() => { void handleSaveTracking(); }}
                                disabled={trackingDigits.length !== 14 || isSavingTracking}
                                aria-label={t("actions.saveTracking")}
                              >
                                {isSavingTracking ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                              </button>
                            </BackofficeTooltip>
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <ValueField
                    label={t("labels.returnDay", { value: data.return_day_label })}
                    value={data.status === "new" ? t("messages.new") : data.status === "rejected" ? t("messages.rejected") : "-"}
                  />
                )}
                {data.status === "rejected" ? <ValueField label={t("labels.rejectionReason")} value={data.rejection_reason || "-"} /> : null}
              </div>
            </section>

            <section className="rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="text-sm font-semibold">Новая Почта</p>
              <div className="mt-3 grid gap-2">
                {showShippingData ? (
                  <>
                    <ValueField label={t("fields.city")} value={data.shipping_address.city_label || "-"} />
                    <ValueField label={t("fields.warehouse")} value={data.shipping_address.np_warehouse_text || "-"} />
                  </>
                ) : (
                  <ValueField label={t("fields.warehouse")} value="-" />
                )}
                <ValueField label={t("labels.tracking")} value={data.tracking_number || t("labels.noTtn")} bold />
              </div>
            </section>
          </div>

          {data.items.length > 0 ? (
            <section className="mt-3 rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <p className="text-sm font-semibold">{t("labels.items")}</p>
              <div className="mt-3 overflow-x-auto rounded-md border" style={{ borderColor: "var(--border)" }}>
                <table className="min-w-full border-separate border-spacing-0 text-xs">
                  <thead style={{ backgroundColor: "var(--surface-2)", color: "var(--muted)" }}>
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">{t("table.sku")}</th>
                      <th className="px-3 py-2 text-left font-medium">{t("table.brand")}</th>
                      <th className="px-3 py-2 text-left font-medium">{t("table.article")}</th>
                      <th className="px-3 py-2 text-left font-medium">{t("table.name")}</th>
                      <th className="px-3 py-2 text-right font-medium">{t("table.qty")}</th>
                      <th className="px-3 py-2 text-right font-medium">{t("table.total")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((item) => {
                      const isNotApproved = item.quantity_requested > 0 && item.quantity_approved <= 0;
                      return (
                        <tr key={item.id} className={isNotApproved ? "opacity-45" : ""} style={{ borderTop: "1px solid var(--border)" }}>
                          <td className="px-3 py-2">{item.display_sku || "-"}</td>
                          <td className="px-3 py-2">{item.display_brand || "-"}</td>
                          <td className="px-3 py-2">{item.display_article || "-"}</td>
                          <td className="px-3 py-2">{item.display_name || item.product_name_snapshot || "-"}</td>
                          <td className="px-3 py-2 text-right">{item.quantity_requested}</td>
                          <td className="px-3 py-2 text-right">{formatReturnMoney(item.refund_amount, locale)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </article>
      ) : null}
    </section>
  );
}
