"use client";

import { useCallback, useMemo, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { getBackofficeAutoDbSupplierBrands } from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeAutoDbSupplierBrand } from "@/features/backoffice/types/backoffice";

export function BrandsPage() {
  const t = useTranslations("backoffice.common");
  const locale = useLocale();

  const [query, setQuery] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState("");
  const [page, setPage] = useState(1);

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeAutoDbSupplierBrands(token, {
        q: query,
        is_active: isActiveFilter,
        page,
      }),
    [isActiveFilter, page, query],
  );

  const { data, isLoading, error } = useBackofficeQuery<{ count: number; results: BackofficeAutoDbSupplierBrand[] }>(queryFn, [
    query,
    isActiveFilter,
    page,
  ]);
  const articleCountLabel = useMemo(() => {
    try {
      return t("brands.table.columns.articleCount");
    } catch {
      return t("brands.table.columns.updated");
    }
  }, [t]);

  const rows = useMemo(() => data?.results ?? [], [data?.results]);
  const pagesCount = useMemo(() => {
    const total = data?.count ?? 0;
    return Math.max(1, Math.ceil(total / 20));
  }, [data?.count]);
  const numberFormatter = useMemo(() => new Intl.NumberFormat(locale), [locale]);

  return (
    <section>
      <PageHeader title={t("brands.title")} description={t("brands.subtitle")} />

      <section className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(1);
          }}
          placeholder={t("brands.filters.search")}
          className="h-9 min-w-[260px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={isActiveFilter}
          onChange={(event) => {
            setIsActiveFilter(event.target.value);
            setPage(1);
          }}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("brands.filters.all")}</option>
          <option value="true">{t("brands.filters.active")}</option>
          <option value="false">{t("brands.filters.inactive")}</option>
        </select>
      </section>

      <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("brands.states.empty")}>
        <BackofficeTable
          emptyLabel={t("brands.states.empty")}
          rows={rows}
          getRowKey={(item) => item.id}
          columns={[
            {
              key: "name",
              label: t("brands.table.columns.name"),
              render: (item) => (
                <div>
                  <p className="font-semibold">{item.name}</p>
                  {item.matchcode ? (
                    <p className="text-xs" style={{ color: "var(--muted)" }}>
                      {item.matchcode}
                    </p>
                  ) : null}
                </div>
              ),
            },
            {
              key: "status",
              label: t("brands.table.columns.status"),
              render: (item) => (
                <BackofficeStatusChip tone={item.is_active ? "success" : "gray"} icon={item.is_active ? CheckCircle2 : XCircle}>
                  {item.is_active ? t("statuses.active") : t("statuses.inactive")}
                </BackofficeStatusChip>
              ),
            },
            {
              key: "updated",
              label: articleCountLabel,
              render: (item) => <span>{numberFormatter.format(item.article_count)}</span>,
            },
          ]}
        />

        <div className="mt-3 flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
          <span>{t("brands.pagination.total", { count: data?.count ?? 0 })}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page <= 1}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            >
              {t("brands.pagination.prev")}
            </button>
            <span>{t("brands.pagination.page", { current: page, total: pagesCount })}</span>
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page >= pagesCount}
              onClick={() => setPage((prev) => Math.min(pagesCount, prev + 1))}
            >
              {t("brands.pagination.next")}
            </button>
          </div>
        </div>
      </AsyncState>
    </section>
  );
}
