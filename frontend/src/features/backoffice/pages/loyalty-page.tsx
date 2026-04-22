"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, CheckCircle2, Copy, Minus, Plus, RefreshCw } from "lucide-react";
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
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { PercentStepper } from "@/features/backoffice/components/pricing/percent-stepper";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeLoyaltyCustomerOption } from "@/features/backoffice/types/backoffice";

const DISCOUNT_TYPE_DELIVERY = "delivery_fee";
const DISCOUNT_TYPE_PRODUCT = "product_markup";

function clampUsageLimit(value: number): number {
  if (!Number.isFinite(value)) {
    return 1;
  }
  return Math.max(1, Math.min(9999, Math.trunc(value)));
}

function parseUsageLimitInput(raw: string, fallback: number): number {
  const normalized = raw.trim().replace(/[^0-9]/g, "");
  if (!normalized) {
    return 1;
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    return clampUsageLimit(fallback);
  }
  return clampUsageLimit(parsed);
}

function formatCustomerDisplay(option: BackofficeLoyaltyCustomerOption): string {
  const primary = (option.label || option.full_name || option.email || "").trim();
  const email = (option.email || "").trim();
  if (!primary) {
    return email;
  }
  if (!email || primary.toLowerCase() === email.toLowerCase()) {
    return primary;
  }
  return `${primary} · ${email}`;
}

export function LoyaltyPage() {
  const t = useTranslations("backoffice.common");
  const { showApiError, showInfo, showSuccess } = useBackofficeFeedback();

  const issuanceQuery = useCallback((token: string) => getBackofficeLoyaltyIssuances(token, 25), []);
  const statsQuery = useCallback((token: string) => getBackofficeLoyaltyStats(token, 14), []);

  const issuances = useBackofficeQuery(issuanceQuery, []);
  const stats = useBackofficeQuery(statsQuery, []);

  const [customerQuery, setCustomerQuery] = useState("");
  const [customerOptions, setCustomerOptions] = useState<BackofficeLoyaltyCustomerOption[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<BackofficeLoyaltyCustomerOption | null>(null);
  const [isCustomerLoading, setIsCustomerLoading] = useState(false);
  const [isCustomerDropdownOpen, setIsCustomerDropdownOpen] = useState(false);
  const [highlightedCustomerIndex, setHighlightedCustomerIndex] = useState(-1);
  const customerComboboxRef = useRef<HTMLDivElement | null>(null);

  const [reason, setReason] = useState("");
  const [discountType, setDiscountType] = useState<typeof DISCOUNT_TYPE_DELIVERY | typeof DISCOUNT_TYPE_PRODUCT>(DISCOUNT_TYPE_DELIVERY);
  const [discountPercent, setDiscountPercent] = useState(15);
  const [expiresAt, setExpiresAt] = useState("");
  const [usageLimit, setUsageLimit] = useState(1);
  const [isIssuing, setIsIssuing] = useState(false);
  const [lastIssuedCode, setLastIssuedCode] = useState("");

  useEffect(() => {
    if (!issuances.token) {
      setCustomerOptions([]);
      setIsCustomerLoading(false);
      return;
    }

    const normalized = customerQuery.trim();
    if (normalized.length < 2) {
      setCustomerOptions([]);
      setIsCustomerLoading(false);
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
      } catch (error) {
        if (mounted) {
          setCustomerOptions([]);
          showApiError(error, t("requestFailed"));
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

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }
      if (!customerComboboxRef.current?.contains(target)) {
        setIsCustomerDropdownOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, []);

  useEffect(() => {
    if (!isCustomerDropdownOpen) {
      return;
    }
    if (customerOptions.length === 0) {
      setHighlightedCustomerIndex(-1);
      return;
    }
    setHighlightedCustomerIndex((current) => {
      if (current < 0 || current >= customerOptions.length) {
        return 0;
      }
      return current;
    });
  }, [customerOptions, isCustomerDropdownOpen]);

  function getDiscountTypeLabel(value: string): string {
    return value === DISCOUNT_TYPE_DELIVERY ? t("loyalty.types.delivery") : t("loyalty.types.product");
  }

  function getDiscountTypeTableLabel(value: string): string {
    return value === DISCOUNT_TYPE_DELIVERY ? t("loyalty.issuances.types.delivery") : t("loyalty.issuances.types.product");
  }

  async function handleIssuePromo() {
    if (!issuances.token || !selectedCustomer) {
      return;
    }
    const customerId = Number(selectedCustomer.id);
    if (!Number.isFinite(customerId)) {
      return;
    }

    setIsIssuing(true);
    try {
      const response = await issueBackofficeLoyaltyPromo(issuances.token, {
        customer_id: customerId,
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

  function handleCustomerSelect(option: BackofficeLoyaltyCustomerOption) {
    setSelectedCustomer(option);
    setCustomerQuery(formatCustomerDisplay(option));
    setIsCustomerDropdownOpen(false);
    setHighlightedCustomerIndex(-1);
    showInfo(t("loyalty.issue.selectedCustomer", { label: option.label || option.email }));
  }

  const isCustomerDropdownVisible =
    isCustomerDropdownOpen && (isCustomerLoading || customerOptions.length > 0 || customerQuery.trim().length >= 2);

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

      <div className="grid gap-4">
        <div className="grid gap-4 xl:grid-cols-[370px_1fr] xl:items-stretch">
          <section className="self-start rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <h2 className="text-sm font-semibold">{t("loyalty.issue.title")}</h2>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("loyalty.issue.subtitle")}</p>

            <div className="mt-3 grid gap-2 text-xs">
              <div className="grid gap-1" ref={customerComboboxRef}>
                <span>{t("loyalty.issue.fields.customer")}</span>
                <div className="relative">
                  <input
                    value={customerQuery}
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setCustomerQuery(nextValue);
                      setIsCustomerDropdownOpen(true);
                      if (selectedCustomer && nextValue !== formatCustomerDisplay(selectedCustomer)) {
                        setSelectedCustomer(null);
                      }
                    }}
                    onFocus={() => {
                      setIsCustomerDropdownOpen(true);
                    }}
                    onBlur={() => {
                      window.setTimeout(() => {
                        setIsCustomerDropdownOpen(false);
                      }, 120);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "ArrowDown") {
                        event.preventDefault();
                        setIsCustomerDropdownOpen(true);
                        setHighlightedCustomerIndex((current) => {
                          const maxIndex = customerOptions.length - 1;
                          if (maxIndex < 0) {
                            return -1;
                          }
                          if (current < 0) {
                            return 0;
                          }
                          return Math.min(maxIndex, current + 1);
                        });
                        return;
                      }
                      if (event.key === "ArrowUp") {
                        event.preventDefault();
                        setIsCustomerDropdownOpen(true);
                        setHighlightedCustomerIndex((current) => {
                          const maxIndex = customerOptions.length - 1;
                          if (maxIndex < 0) {
                            return -1;
                          }
                          if (current < 0) {
                            return maxIndex;
                          }
                          return Math.max(0, current - 1);
                        });
                        return;
                      }
                      if (event.key === "Enter" && isCustomerDropdownOpen) {
                        if (highlightedCustomerIndex >= 0 && highlightedCustomerIndex < customerOptions.length) {
                          event.preventDefault();
                          handleCustomerSelect(customerOptions[highlightedCustomerIndex]);
                        }
                        return;
                      }
                      if (event.key === "Escape") {
                        setIsCustomerDropdownOpen(false);
                      }
                    }}
                    placeholder={t("loyalty.issue.placeholders.customerSearch")}
                    className="h-9 w-full rounded-md border px-3 pr-24"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    role="combobox"
                    aria-expanded={isCustomerDropdownVisible}
                    aria-controls="loyalty-customer-listbox"
                    aria-autocomplete="list"
                  />

                  {selectedCustomer ? (
                    <span className="pointer-events-none absolute right-2 top-1/2 inline-flex -translate-y-1/2">
                      <BackofficeTooltip
                        content={t("loyalty.states.selected")}
                        placement="top"
                        align="center"
                        wrapperClassName="inline-flex"
                        tooltipClassName="whitespace-nowrap"
                      >
                        <BackofficeStatusChip
                          tone="success"
                          icon={CheckCircle2}
                          className="cursor-help justify-center gap-0 px-1.5 [&>span:last-child]:hidden"
                        >
                          <span className="sr-only">{t("loyalty.states.selected")}</span>
                        </BackofficeStatusChip>
                      </BackofficeTooltip>
                    </span>
                  ) : null}

                  {isCustomerDropdownVisible ? (
                    <div
                      id="loyalty-customer-listbox"
                      role="listbox"
                      className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-md border p-1"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    >
                      {isCustomerLoading ? (
                        <div className="px-2 py-2 text-xs" style={{ color: "var(--muted)" }}>
                          {t("loyalty.states.loadingCustomers")}
                        </div>
                      ) : customerOptions.length > 0 ? (
                        customerOptions.map((item, index) => {
                          const isHighlighted = index === highlightedCustomerIndex;
                          const isSelected = selectedCustomer?.id === item.id;
                          return (
                            <button
                              key={item.id}
                              type="button"
                              role="option"
                              aria-selected={isSelected}
                              className="flex w-full items-start justify-between rounded-md px-2 py-2 text-left text-xs"
                              style={{
                                backgroundColor: isHighlighted ? "var(--surface-2)" : "transparent",
                              }}
                              onMouseDown={(event) => {
                                event.preventDefault();
                                handleCustomerSelect(item);
                              }}
                              onMouseEnter={() => {
                                setHighlightedCustomerIndex(index);
                              }}
                            >
                              <span className="min-w-0">
                                <span className="block truncate font-semibold">{item.label || item.full_name || item.email}</span>
                                <span className="block truncate" style={{ color: "var(--muted)" }}>
                                  {item.email}
                                </span>
                              </span>
                              {isSelected ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : null}
                            </button>
                          );
                        })
                      ) : (
                        <div className="px-2 py-2 text-xs" style={{ color: "var(--muted)" }}>
                          {t("loyalty.states.customersEmpty")}
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              </div>

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

              <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <div className="grid w-fit gap-1 sm:shrink-0">
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

                <label className="grid gap-1 min-w-0 sm:flex-1">
                  <span>{t("loyalty.issue.fields.type")}</span>
                  <select
                    value={discountType}
                    onChange={(event) => setDiscountType(event.target.value as typeof DISCOUNT_TYPE_DELIVERY | typeof DISCOUNT_TYPE_PRODUCT)}
                    className="h-9 w-full rounded-md border px-3"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  >
                    <option value={DISCOUNT_TYPE_DELIVERY}>{getDiscountTypeLabel(DISCOUNT_TYPE_DELIVERY)}</option>
                    <option value={DISCOUNT_TYPE_PRODUCT}>{getDiscountTypeLabel(DISCOUNT_TYPE_PRODUCT)}</option>
                  </select>
                </label>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <div className="inline-grid w-fit gap-1 sm:shrink-0">
                  <span>{t("loyalty.issue.fields.usageLimit")}</span>
                  <div
                    className="inline-flex h-9 w-fit items-center rounded-full border px-1"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  >
                    <button
                      type="button"
                      className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                      aria-label={t("loyalty.issue.actions.usageLimitMinus")}
                      onClick={() => setUsageLimit((current) => clampUsageLimit(current - 1))}
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </button>

                    <label className="relative inline-flex items-center px-1">
                      <input
                        type="text"
                        inputMode="numeric"
                        autoComplete="off"
                        value={usageLimit}
                        aria-label={t("loyalty.issue.fields.usageLimit")}
                        className="h-7 w-16 border-0 bg-transparent px-1 text-center text-sm font-semibold outline-none"
                        onChange={(event) => setUsageLimit(parseUsageLimitInput(event.target.value, usageLimit))}
                      />
                    </label>

                    <button
                      type="button"
                      className="inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors hover:opacity-90"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                      aria-label={t("loyalty.issue.actions.usageLimitPlus")}
                      onClick={() => setUsageLimit((current) => clampUsageLimit(current + 1))}
                    >
                      <Plus className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                <label className="grid gap-1 min-w-0 sm:flex-1">
                  <span>{t("loyalty.issue.fields.expiresAt")}</span>
                  <input
                    type="datetime-local"
                    value={expiresAt}
                    onChange={(event) => setExpiresAt(event.target.value)}
                    className="h-9 w-full rounded-md border px-3"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  />
                </label>
              </div>

              <button
                type="button"
                disabled={isIssuing || !selectedCustomer || !reason.trim()}
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
                    <BackofficeTooltip
                      content={t("loyalty.actions.copy")}
                      placement="top"
                      align="center"
                      wrapperClassName="inline-flex"
                      tooltipClassName="whitespace-nowrap"
                    >
                      <button
                        type="button"
                        aria-label={t("loyalty.actions.copy")}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-md border text-xs"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                        onClick={() => {
                          void handleCopyCode(lastIssuedCode);
                        }}
                      >
                        <Copy size={14} />
                      </button>
                    </BackofficeTooltip>
                  </div>
                </div>
              ) : null}
            </div>
          </section>

          <AsyncState
            isLoading={issuances.isLoading || stats.isLoading}
            error={null}
            empty={!issuances.data || !stats.data}
            emptyLabel={t("loyalty.states.empty")}
          >
            {issuances.data && stats.data ? (
              <section className="flex h-full flex-col rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="text-sm font-semibold">{t("loyalty.chart.title")}</h2>
                  <span className="text-xs" style={{ color: "var(--muted)" }}>{t("loyalty.chart.subtitle")}</span>
                </div>
                <div className="mt-1 h-[210px] xl:h-auto xl:flex-1">
                  <LoyaltyDailyChart
                    items={stats.data.chart.by_day}
                    emptyLabel={t("loyalty.states.chartEmpty")}
                    className="h-full w-full"
                    emptyClassName="h-full"
                  />
                </div>
              </section>
            ) : null}
          </AsyncState>
        </div>

        {issuances.data && stats.data ? (
          <div className="grid gap-4">
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
                          <BackofficeTooltip
                            content={t("loyalty.actions.copy")}
                            placement="top"
                            align="center"
                            wrapperClassName="inline-flex"
                            tooltipClassName="whitespace-nowrap"
                          >
                            <button
                              type="button"
                              aria-label={t("loyalty.actions.copy")}
                              className="inline-flex h-7 w-7 items-center justify-center rounded border text-xs"
                              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                              onClick={() => {
                                void handleCopyCode(item.code);
                              }}
                            >
                              <Copy size={12} />
                            </button>
                          </BackofficeTooltip>
                        </div>
                      ),
                    },
                    { key: "customer", label: t("loyalty.issuances.columns.customer"), render: (item) => item.customer.name || item.customer.email },
                    { key: "type", label: t("loyalty.issuances.columns.type"), render: (item) => getDiscountTypeTableLabel(item.discount_type) },
                    { key: "size", label: t("loyalty.issuances.columns.size"), render: (item) => `${item.discount_percent}%` },
                    { key: "issuer", label: t("loyalty.issuances.columns.issuer"), render: (item) => item.issued_by.name || item.issued_by.email || "-" },
                    { key: "reason", label: t("loyalty.issuances.columns.reason"), render: (item) => item.reason },
                    { key: "issuedAt", label: t("loyalty.issuances.columns.issuedAt"), render: (item) => new Date(item.issued_at).toLocaleString() },
                    { key: "expiresAt", label: t("loyalty.issuances.columns.expiresAt"), render: (item) => (item.expires_at ? new Date(item.expires_at).toLocaleString() : "-") },
                    { key: "used", label: t("loyalty.issuances.columns.used"), render: (item) => (item.is_used ? t("yes") : t("no")) },
                    { key: "state", label: t("loyalty.issuances.columns.state"), render: (item) => <StatusChip status={item.state} /> },
                  ]}
                />
              </div>
            </section>
          </div>
        ) : null}
      </div>
    </section>
  );
}
