"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Copy, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  getBackofficeLoyaltyCustomers,
  getBackofficeLoyaltyIssuances,
  getBackofficeLoyaltyStats,
  issueBackofficeLoyaltyPromo,
} from "@/features/backoffice/api/backoffice-api";
import { LoyaltyDailyChart } from "@/features/backoffice/components/loyalty/loyalty-daily-chart";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { PercentStepper } from "@/features/backoffice/components/pricing/percent-stepper";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeLoyaltyCustomerOption } from "@/features/backoffice/types/backoffice";

const DISCOUNT_TYPE_DELIVERY = "delivery_fee";
const DISCOUNT_TYPE_PRODUCT = "product_markup";

export function LoyaltyPage() {
  const t = useTranslations("backoffice.common");
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const issuanceQuery = useCallback((token: string) => getBackofficeLoyaltyIssuances(token, 25), []);
  const statsQuery = useCallback((token: string) => getBackofficeLoyaltyStats(token, 14), []);

  const issuances = useBackofficeQuery(issuanceQuery, []);
  const stats = useBackofficeQuery(statsQuery, []);

  const [customerQuery, setCustomerQuery] = useState("");
  const [customerOptions, setCustomerOptions] = useState<BackofficeLoyaltyCustomerOption[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [isCustomerLoading, setIsCustomerLoading] = useState(false);

  const [reason, setReason] = useState("");
  const [discountType, setDiscountType] = useState<typeof DISCOUNT_TYPE_DELIVERY | typeof DISCOUNT_TYPE_PRODUCT>(DISCOUNT_TYPE_DELIVERY);
  const [discountPercent, setDiscountPercent] = useState(15);
  const [expiresAt, setExpiresAt] = useState("");
  const [usageLimit, setUsageLimit] = useState(1);
  const [isIssuing, setIsIssuing] = useState(false);
  const [lastIssuedCode, setLastIssuedCode] = useState("");

  const selectedCustomer = useMemo(
    () => customerOptions.find((item) => item.id === selectedCustomerId) || null,
    [customerOptions, selectedCustomerId],
  );

  useEffect(() => {
    if (!issuances.token) {
      setCustomerOptions([]);
      return;
    }

    const normalized = customerQuery.trim();
    if (normalized.length < 2) {
      setCustomerOptions([]);
      return;
    }

    let mounted = true;
    setIsCustomerLoading(true);
    const timeoutId = window.setTimeout(async () => {
      try {
        const response = await getBackofficeLoyaltyCustomers(issuances.token as string, normalized);
        if (mounted) {
          setCustomerOptions(response.results);
        }
      } catch {
        if (mounted) {
          setCustomerOptions([]);
        }
      } finally {
        if (mounted) {
          setIsCustomerLoading(false);
        }
      }
    }, 250);

    return () => {
      mounted = false;
      window.clearTimeout(timeoutId);
    };
  }, [customerQuery, issuances.token]);

  function getDiscountTypeLabel(value: string): string {
    return value === DISCOUNT_TYPE_DELIVERY ? t("loyalty.types.delivery") : t("loyalty.types.product");
  }

  function getStateLabel(value: string): string {
    if (value === "active") {
      return t("loyalty.states.active");
    }
    if (value === "used") {
      return t("loyalty.states.used");
    }
    if (value === "expired") {
      return t("loyalty.states.expired");
    }
    return t("loyalty.states.disabled");
  }

  async function handleIssuePromo() {
    if (!issuances.token || !selectedCustomerId) {
      return;
    }

    setIsIssuing(true);
    try {
      const response = await issueBackofficeLoyaltyPromo(issuances.token, {
        customer_id: Number(selectedCustomerId),
        reason: reason.trim(),
        discount_type: discountType,
        discount_percent: discountPercent,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
        usage_limit: Math.max(1, usageLimit),
      });

      setLastIssuedCode(response.code);
      showSuccess(t("loyalty.messages.issued", { code: response.code }));
      setReason("");
      setUsageLimit(1);
      await Promise.all([issuances.refetch(), stats.refetch()]);
    } catch (error) {
      showApiError(error, t("loyalty.messages.issueFailed"));
    } finally {
      setIsIssuing(false);
    }
  }

  async function handleCopyCode(code: string) {
    if (!code) {
      return;
    }
    try {
      await navigator.clipboard.writeText(code);
      showSuccess(t("loyalty.messages.codeCopied"));
    } catch {
      // Silent fallback: clipboard may be restricted.
    }
  }

  return (
    <section>
      <PageHeader
        title={t("loyalty.title")}
        description={t("loyalty.subtitle")}
        actions={
          <button
            type="button"
            className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void Promise.all([issuances.refetch(), stats.refetch()]);
            }}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.1s" }} />
            {t("loyalty.actions.refresh")}
          </button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[370px_1fr]">
        <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <h2 className="text-sm font-semibold">{t("loyalty.issue.title")}</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("loyalty.issue.subtitle")}</p>

          <div className="mt-3 grid gap-2 text-xs">
            <label className="grid gap-1">
              <span>{t("loyalty.issue.fields.customerSearch")}</span>
              <input
                value={customerQuery}
                onChange={(event) => setCustomerQuery(event.target.value)}
                placeholder={t("loyalty.issue.placeholders.customerSearch")}
                className="h-9 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>

            <label className="grid gap-1">
              <span>{t("loyalty.issue.fields.customer")}</span>
              <select
                value={selectedCustomerId}
                onChange={(event) => setSelectedCustomerId(event.target.value)}
                className="h-9 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              >
                <option value="">{isCustomerLoading ? t("loyalty.states.loadingCustomers") : t("loyalty.issue.placeholders.customer")}</option>
                {customerOptions.map((item) => (
                  <option key={item.id} value={item.id}>{item.label} ({item.email})</option>
                ))}
              </select>
            </label>

            <label className="grid gap-1">
              <span>{t("loyalty.issue.fields.reason")}</span>
              <input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder={t("loyalty.issue.placeholders.reason")}
                className="h-9 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>

            <label className="grid gap-1">
              <span>{t("loyalty.issue.fields.type")}</span>
              <select
                value={discountType}
                onChange={(event) => setDiscountType(event.target.value as typeof DISCOUNT_TYPE_DELIVERY | typeof DISCOUNT_TYPE_PRODUCT)}
                className="h-9 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              >
                <option value={DISCOUNT_TYPE_DELIVERY}>{t("loyalty.types.delivery")}</option>
                <option value={DISCOUNT_TYPE_PRODUCT}>{t("loyalty.types.product")}</option>
              </select>
            </label>

            <div className="grid gap-1">
              <span>{t("loyalty.issue.fields.percent")}</span>
              <PercentStepper
                value={discountPercent}
                onChange={setDiscountPercent}
                min={0}
                max={100}
                step={1}
                minusLabel={t("loyalty.issue.actions.percentMinus")}
                plusLabel={t("loyalty.issue.actions.percentPlus")}
                inputLabel={t("loyalty.issue.fields.percent")}
              />
            </div>

            <label className="grid gap-1">
              <span>{t("loyalty.issue.fields.expiresAt")}</span>
              <input
                type="datetime-local"
                value={expiresAt}
                onChange={(event) => setExpiresAt(event.target.value)}
                className="h-9 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>

            <label className="grid gap-1">
              <span>{t("loyalty.issue.fields.usageLimit")}</span>
              <input
                type="number"
                min={1}
                value={usageLimit}
                onChange={(event) => setUsageLimit(Math.max(1, Number(event.target.value || "1")))}
                className="h-9 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>

            <button
              type="button"
              disabled={isIssuing || !selectedCustomerId || !reason.trim()}
              className="mt-2 inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-semibold disabled:opacity-60"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void handleIssuePromo();
              }}
            >
              {isIssuing ? t("loyalty.issue.actions.issuing") : t("loyalty.issue.actions.issue")}
            </button>

            {lastIssuedCode ? (
              <div className="mt-2 rounded-lg border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                <p className="text-xs" style={{ color: "var(--muted)" }}>{t("loyalty.issue.lastIssued")}</p>
                <div className="mt-1 flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold">{lastIssuedCode}</p>
                  <button
                    type="button"
                    className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    onClick={() => {
                      void handleCopyCode(lastIssuedCode);
                    }}
                  >
                    <Copy size={14} />
                    {t("loyalty.actions.copy")}
                  </button>
                </div>
              </div>
            ) : null}

            {selectedCustomer ? (
              <p className="text-xs" style={{ color: "var(--muted)" }}>
                {t("loyalty.issue.selectedCustomer", { label: selectedCustomer.label || selectedCustomer.email })}
              </p>
            ) : null}
          </div>
        </section>

        <AsyncState
          isLoading={issuances.isLoading || stats.isLoading}
          error={issuances.error || stats.error}
          empty={!issuances.data || !stats.data}
          emptyLabel={t("loyalty.states.empty")}
        >
          {issuances.data && stats.data ? (
            <div className="grid gap-4">
              <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="text-sm font-semibold">{t("loyalty.chart.title")}</h2>
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{t("loyalty.chart.subtitle")}</span>
                </div>
                <LoyaltyDailyChart items={stats.data.chart.by_day} emptyLabel={t("loyalty.states.chartEmpty")} />
              </section>

              <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("loyalty.stats.title")}</h2>
                <div className="mt-3">
                  <BackofficeTable
                    rows={stats.data.staff}
                    emptyLabel={t("loyalty.states.statsEmpty")}
                    noHorizontalScroll
                    columns={[
                      {
                        key: "staff",
                        label: t("loyalty.stats.columns.staff"),
                        render: (item) => (
                          <div>
                            <p className="font-semibold">{item.staff_name || item.staff_email}</p>
                            <p className="text-xs" style={{ color: "var(--muted)" }}>{item.staff_email}</p>
                          </div>
                        ),
                      },
                      { key: "issued", label: t("loyalty.stats.columns.issued"), render: (item) => item.issued_total },
                      { key: "delivery", label: t("loyalty.stats.columns.delivery"), render: (item) => item.issued_delivery },
                      { key: "product", label: t("loyalty.stats.columns.product"), render: (item) => item.issued_product },
                      { key: "nominal", label: t("loyalty.stats.columns.nominal"), render: (item) => item.nominal_percent_total },
                      { key: "used", label: t("loyalty.stats.columns.used"), render: (item) => item.used_total },
                      { key: "conversion", label: t("loyalty.stats.columns.conversion"), render: (item) => `${item.conversion_rate}%` },
                    ]}
                  />
                </div>
              </section>

              <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <h2 className="text-sm font-semibold">{t("loyalty.issuances.title")}</h2>
                <div className="mt-3">
                  <BackofficeTable
                    rows={issuances.data}
                    emptyLabel={t("loyalty.states.issuancesEmpty")}
                    columns={[
                      {
                        key: "code",
                        label: t("loyalty.issuances.columns.code"),
                        render: (item) => (
                          <div className="flex items-center gap-2">
                            <p className="font-semibold">{item.code}</p>
                            <button
                              type="button"
                              className="inline-flex h-7 items-center gap-1 rounded border px-2 text-xs"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                              onClick={() => {
                                void handleCopyCode(item.code);
                              }}
                            >
                              <Copy size={12} />
                              {t("loyalty.actions.copy")}
                            </button>
                          </div>
                        ),
                      },
                      { key: "customer", label: t("loyalty.issuances.columns.customer"), render: (item) => item.customer.name || item.customer.email },
                      { key: "type", label: t("loyalty.issuances.columns.type"), render: (item) => getDiscountTypeLabel(item.discount_type) },
                      { key: "size", label: t("loyalty.issuances.columns.size"), render: (item) => `${item.discount_percent}%` },
                      { key: "issuer", label: t("loyalty.issuances.columns.issuer"), render: (item) => item.issued_by.name || item.issued_by.email || "-" },
                      { key: "reason", label: t("loyalty.issuances.columns.reason"), render: (item) => item.reason },
                      { key: "issuedAt", label: t("loyalty.issuances.columns.issuedAt"), render: (item) => new Date(item.issued_at).toLocaleString() },
                      { key: "expiresAt", label: t("loyalty.issuances.columns.expiresAt"), render: (item) => (item.expires_at ? new Date(item.expires_at).toLocaleString() : "-") },
                      { key: "used", label: t("loyalty.issuances.columns.used"), render: (item) => (item.is_used ? t("yes") : t("no")) },
                      { key: "state", label: t("loyalty.issuances.columns.state"), render: (item) => getStateLabel(item.state) },
                    ]}
                  />
                </div>
              </section>
            </div>
          ) : null}
        </AsyncState>
      </div>
    </section>
  );
}
