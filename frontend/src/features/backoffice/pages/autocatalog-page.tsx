"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeAutocatalog, getBackofficeAutocatalogFilterOptions } from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeAutocatalogCar, BackofficeAutocatalogFilterOptions } from "@/features/backoffice/types/backoffice";

const PAGE_SIZE_OPTIONS = [15, 25, 50, 100, 500] as const;

function asText(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim();
  return normalized || "-";
}

function asNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : String(value);
}

function asYear(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim();
  if (!normalized) {
    return "-";
  }
  const match = normalized.match(/^\d{4}/);
  return match ? match[0] : normalized;
}

export function AutocatalogPage() {
  const t = useTranslations("backoffice.autocatalog");

  const [isHydrated, setIsHydrated] = useState(false);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [year, setYear] = useState("");
  const [modification, setModification] = useState("");
  const [engine, setEngine] = useState("");
  const [capacity, setCapacity] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(25);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedQ(q);
    }, 300);
    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [q]);

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeAutocatalog(token, {
        q: debouncedQ,
        make,
        model,
        year,
        modification,
        engine,
        capacity,
        page,
        page_size: pageSize,
      }),
    [capacity, debouncedQ, engine, make, model, modification, page, pageSize, year],
  );

  const { data, isLoading, error } = useBackofficeQuery<{ count: number; results: BackofficeAutocatalogCar[] }>(queryFn, [
    debouncedQ,
    make,
    model,
    year,
    modification,
    engine,
    capacity,
    page,
    pageSize,
  ]);

  const filterOptionsQuery = useCallback(
    (token: string) =>
      getBackofficeAutocatalogFilterOptions(token, {
        year,
        make,
        model,
        modification,
        capacity,
      }),
    [capacity, make, model, modification, year],
  );

  const { data: filterOptions } = useBackofficeQuery<BackofficeAutocatalogFilterOptions>(filterOptionsQuery, [
    year,
    make,
    model,
    modification,
    capacity,
  ]);

  const rows = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const pagesCount = useMemo(() => Math.max(1, Math.ceil(totalCount / pageSize)), [pageSize, totalCount]);

  return (
    <section>
      <PageHeader title={t("title")} description={t("subtitle")} />

      <div className="mb-3 grid gap-2 xl:grid-cols-[minmax(280px,1.5fr)_140px_repeat(6,minmax(120px,1fr))]">
        <input
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(1);
          }}
          placeholder={t("search")}
          className="h-10 min-w-[280px] flex-1 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={String(pageSize)}
          onChange={(event) => {
            const nextSize = Number(event.target.value) as (typeof PAGE_SIZE_OPTIONS)[number];
            setPageSize(nextSize);
            setPage(1);
          }}
          className="h-10 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          {PAGE_SIZE_OPTIONS.map((sizeOption) => (
            <option key={sizeOption} value={sizeOption}>
              {`${t("pagination.perPage")}: ${sizeOption}`}
            </option>
          ))}
        </select>

        <select
          value={year}
          onChange={(event) => {
            setYear(event.target.value);
            setMake("");
            setModel("");
            setModification("");
            setCapacity("");
            setEngine("");
            setPage(1);
          }}
          className="h-10 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allYears")}</option>
          {(filterOptions?.years ?? []).map((value) => (
            <option key={value} value={String(value)}>
              {value}
            </option>
          ))}
        </select>

        <select
          value={make}
          onChange={(event) => {
            setMake(event.target.value);
            setModel("");
            setModification("");
            setCapacity("");
            setEngine("");
            setPage(1);
          }}
          className="h-10 rounded-md border px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allMakes")}</option>
          {(filterOptions?.makes ?? []).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>

        <select
          value={model}
          onChange={(event) => {
            setModel(event.target.value);
            setModification("");
            setCapacity("");
            setEngine("");
            setPage(1);
          }}
          disabled={isHydrated ? !make : undefined}
          className="h-10 rounded-md border px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allModels")}</option>
          {(filterOptions?.models ?? []).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>

        <select
          value={modification}
          onChange={(event) => {
            setModification(event.target.value);
            setCapacity("");
            setEngine("");
            setPage(1);
          }}
          disabled={isHydrated ? (!make || !model) : undefined}
          className="h-10 rounded-md border px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allModifications")}</option>
          {(filterOptions?.modifications ?? []).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>

        <select
          value={capacity}
          onChange={(event) => {
            setCapacity(event.target.value);
            setEngine("");
            setPage(1);
          }}
          disabled={isHydrated ? (!make || !model || !modification) : undefined}
          className="h-10 rounded-md border px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allCapacities")}</option>
          {(filterOptions?.capacities ?? []).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>

        <select
          value={engine}
          onChange={(event) => {
            setEngine(event.target.value);
            setPage(1);
          }}
          disabled={isHydrated ? (!make || !model || !modification || !capacity) : undefined}
          className="h-10 rounded-md border px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("filters.allEngines")}</option>
          {(filterOptions?.engines ?? []).map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </div>

      <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("empty")}>
        <BackofficeTable
          rows={rows}
          emptyLabel={t("empty")}
          columns={[
            {
              key: "year",
              label: t("table.columns.year"),
              render: (item) => asNumber(item.year),
            },
            {
              key: "end_date_at",
              label: t("table.columns.to"),
              render: (item) => asYear(item.end_date_at),
            },
            {
              key: "make",
              label: t("table.columns.make"),
              render: (item) => asText(item.make),
            },
            {
              key: "model",
              label: t("table.columns.model"),
              render: (item) => asText(item.model),
            },
            {
              key: "modification",
              label: t("table.columns.modification"),
              render: (item) => asText(item.modification),
            },
            {
              key: "capacity",
              label: t("table.columns.capacity"),
              render: (item) => asText(item.capacity),
            },
            {
              key: "engine",
              label: t("table.columns.engine"),
              render: (item) => asText(item.engine),
            },
            {
              key: "hp",
              label: t("table.columns.hp"),
              render: (item) => asNumber(item.hp),
            },
            {
              key: "kw",
              label: t("table.columns.kw"),
              render: (item) => asNumber(item.kw),
            },
          ]}
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span>{t("pagination.total", { count: totalCount })}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page <= 1}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            >
              {t("pagination.prev")}
            </button>
            <span>{t("pagination.page", { current: page, total: pagesCount })}</span>
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page >= pagesCount}
              onClick={() => setPage((prev) => Math.min(pagesCount, prev + 1))}
            >
              {t("pagination.next")}
            </button>
          </div>
        </div>
      </AsyncState>
    </section>
  );
}
