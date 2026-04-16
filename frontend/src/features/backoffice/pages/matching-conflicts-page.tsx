"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  applyManualMatchesBackoffice,
  bulkIgnoreBackoffice,
  getBackofficeConflictOffers,
  ignoreBackofficeOffer,
  retryBackofficeMatching,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { Link } from "@/i18n/navigation";

export function MatchingConflictsPage() {
  const t = useTranslations("backoffice.matching.conflicts");
  const [q, setQ] = useState("");
  const [supplier, setSupplier] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const { showApiError, showSuccess, showWarning } = useBackofficeFeedback();

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeConflictOffers(token, {
        q,
        supplier,
      }),
    [q, supplier],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery(queryFn, [q, supplier]);
  const rows = data?.results ?? [];
  const supplierOptions = useMemo(() => Array.from(new Set(rows.map((item) => item.supplier_code))).sort(), [rows]);

  function toggleSelection(rawOfferId: string) {
    setSelectedIds((current) => (current.includes(rawOfferId) ? current.filter((item) => item !== rawOfferId) : [...current, rawOfferId]));
  }

  async function rowRetry(rawOfferId: string) {
    if (!token) return;
    try {
      await retryBackofficeMatching(token, { raw_offer_id: rawOfferId });
      showSuccess(t("messages.retriedOne"));
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("messages.actionFailed"));
    }
  }

  async function rowIgnore(rawOfferId: string) {
    if (!token) return;
    try {
      await ignoreBackofficeOffer(token, { raw_offer_id: rawOfferId });
      showSuccess(t("messages.ignoredOne"));
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("messages.actionFailed"));
    }
  }

  async function bulkIgnore() {
    if (!token || selectedIds.length === 0) return;
    try {
      await bulkIgnoreBackoffice(token, { raw_offer_ids: selectedIds });
      showSuccess(t("messages.bulkIgnored", { count: selectedIds.length }));
      setSelectedIds([]);
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("messages.actionFailed"));
    }
  }

  async function applySelfManual() {
    if (!token || selectedIds.length === 0) return;
    const mappings = rows
      .filter((item) => selectedIds.includes(item.id) && item.match_candidate_product_ids.length === 1)
      .map((item) => ({ raw_offer_id: item.id, product_id: item.match_candidate_product_ids[0] }));

    if (mappings.length === 0) {
      showWarning(t("messages.noSingleCandidate"));
      return;
    }

    try {
      await applyManualMatchesBackoffice(token, { mappings });
      showSuccess(t("messages.manualApplied", { count: mappings.length }));
      setSelectedIds([]);
      await refetch();
    } catch (error: unknown) {
      showApiError(error, t("messages.actionFailed"));
    }
  }

  return (
    <section>
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void applySelfManual();
              }}
              disabled={selectedIds.length === 0}
            >
              {t("actions.applySingleCandidate")}
            </button>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void bulkIgnore();
              }}
              disabled={selectedIds.length === 0}
            >
              {t("actions.bulkIgnore")}
            </button>
          </>
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={t("filters.search")}
          className="h-9 min-w-[220px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={supplier}
          onChange={(event) => setSupplier(event.target.value)}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allSuppliers")}</option>
          {supplierOptions.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>

      <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("states.empty")}>
        <BackofficeTable
          emptyLabel={t("states.empty")}
          rows={rows}
          columns={[
            {
              key: "select",
              label: "",
              render: (item) => (
                <input
                  type="checkbox"
                  checked={selectedIds.includes(item.id)}
                  onChange={() => toggleSelection(item.id)}
                />
              ),
            },
            {
              key: "supplier",
              label: t("table.columns.supplier"),
              render: (item) => item.supplier_code,
            },
            {
              key: "article",
              label: t("table.columns.article"),
              render: (item) => (
                <div>
                  <p className="font-semibold">{item.article || item.external_sku}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {item.brand_name}
                  </p>
                </div>
              ),
            },
            {
              key: "reason",
              label: t("table.columns.reason"),
              render: (item) => <StatusChip status={item.match_reason || item.match_status} />,
            },
            {
              key: "candidates",
              label: t("table.columns.candidates"),
              render: (item) => item.match_candidate_product_ids.length,
            },
            {
              key: "actions",
              label: t("table.columns.actions"),
              render: (item) => (
                <div className="flex flex-wrap gap-1">
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    onClick={() => {
                      void rowRetry(item.id);
                    }}
                  >
                    {t("actions.retry")}
                  </button>
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    onClick={() => {
                      void rowIgnore(item.id);
                    }}
                  >
                    {t("actions.ignore")}
                  </button>
                  <Link href={`/backoffice/matching/review/${item.id}`} className="inline-flex h-8 items-center rounded-md border px-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                    {t("actions.review")}
                  </Link>
                </div>
              ),
            },
          ]}
        />
      </AsyncState>
    </section>
  );
}
