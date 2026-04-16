"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeImportErrors } from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeImportError } from "@/features/backoffice/types/backoffice";

export function ImportErrorsPage() {
  const t = useTranslations("backoffice.importErrors");
  const [q, setQ] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeImportErrors(token, {
        q,
        source: sourceFilter,
      }),
    [q, sourceFilter],
  );

  const { data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeImportError[] }>(queryFn, [q, sourceFilter]);
  const errors = data?.results ?? [];

  const sourceOptions = Array.from(new Set(errors.map((item) => item.source_code))).sort();

  return (
    <section>
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <button
            type="button"
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void refetch();
            }}
          >
            {t("actions.refresh")}
          </button>
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
          value={sourceFilter}
          onChange={(event) => setSourceFilter(event.target.value)}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allSources")}</option>
          {sourceOptions.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </select>
      </div>

      <AsyncState isLoading={isLoading} error={error} empty={!errors.length} emptyLabel={t("states.empty")}>
        <BackofficeTable
          emptyLabel={t("states.empty")}
          rows={errors}
          columns={[
            {
              key: "source",
              label: t("table.columns.source"),
              render: (item) => item.source_code,
            },
            {
              key: "errorCode",
              label: t("table.columns.errorCode"),
              render: (item) => item.error_code || "-",
            },
            {
              key: "sku",
              label: t("table.columns.sku"),
              render: (item) => item.external_sku || "-",
            },
            {
              key: "message",
              label: t("table.columns.message"),
              render: (item) => (
                <p className="max-w-[440px] text-xs" title={item.message}>
                  {item.message}
                </p>
              ),
            },
            {
              key: "created",
              label: t("table.columns.created"),
              render: (item) => new Date(item.created_at).toLocaleString(),
            },
          ]}
        />
      </AsyncState>
    </section>
  );
}
