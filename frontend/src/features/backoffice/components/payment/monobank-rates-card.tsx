"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeMonobankCurrencyResponse } from "@/features/backoffice/types/payment.types";

export function MonobankRatesCard({
  rates,
  isLoading,
  refreshDisabled,
  onRefresh,
  t,
}: {
  rates: BackofficeMonobankCurrencyResponse | null;
  isLoading: boolean;
  refreshDisabled?: boolean;
  onRefresh: () => void;
  t: (key: string) => string;
}) {
  function renderRateValue(value: number | null) {
    return <span className="font-semibold" style={{ color: "var(--text)" }}>{value ?? "-"}</span>;
  }
  const [isHydrated, setIsHydrated] = useState(false);
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  const normalizedLoading = isLoading !== false;
  const normalizedRefreshDisabled = refreshDisabled === true;
  const isRefreshButtonDisabled = isHydrated ? (normalizedLoading || normalizedRefreshDisabled) : undefined;

  return (
    <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">{t("payments.monobank.currencyRates")}</p>
        <BackofficeTooltip content={t("payments.monobank.refreshRates")} placement="top" align="center" wrapperClassName="inline-flex">
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onRefresh}
            disabled={isRefreshButtonDisabled}
            aria-label={t("payments.monobank.refreshRates")}
          >
            <RefreshCw className="h-4 w-4 animate-spin" style={{ animationDuration: "2.2s" }} />
          </button>
        </BackofficeTooltip>
      </div>

      {rates?.rows?.length ? (
        <div className="mt-3 grid gap-2">
          {rates.rows.map((row) => (
            <div key={row.pair} className="rounded-md border px-3 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <p className="font-semibold">{row.pair}</p>
              <p style={{ color: "var(--muted)" }}>
                {t("payments.monobank.rateLabels.buy")}: {renderRateValue(row.rate_buy)} · {t("payments.monobank.rateLabels.sell")}: {renderRateValue(row.rate_sell)} · {t("payments.monobank.rateLabels.cross")}: {renderRateValue(row.rate_cross)}
              </p>
              <p style={{ color: "var(--muted)" }}>{formatBackofficeDate(row.updated_at)}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
