"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  getBackofficeAutoDbVehicleFilterOptions,
  getBackofficeAutoDbVehicles,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { isModelSelectorDisabled, isVehicleTableReady } from "@/features/backoffice/lib/autodb-vehicle-catalog";
import type {
  BackofficeAutoDbVehicleFilterOptions,
  BackofficeAutoDbVehicleRow,
} from "@/features/backoffice/types/backoffice";

const PAGE_SIZE_OPTIONS = [15, 25, 50, 100, 500] as const;

function asText(value: string | null | undefined): string {
  const normalized = String(value ?? "").trim();
  return normalized || "-";
}

export function AutocatalogPage() {
  const t = useTranslations("backoffice.autocatalog");
  const tCommon = useTranslations("backoffice.common");

  const [isHydrated, setIsHydrated] = useState(false);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [manufacturerId, setManufacturerId] = useState("");
  const [modelId, setModelId] = useState("");
  const [year, setYear] = useState("");
  const [modification, setModification] = useState("");
  const [volume, setVolume] = useState("");
  const [engine, setEngine] = useState("");
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

  const filterOptionsQueryFn = useCallback(
    (token: string) =>
      getBackofficeAutoDbVehicleFilterOptions(token, {
        year,
        manufacturer_id: manufacturerId,
        model_id: modelId,
        modification,
        volume,
      }),
    [manufacturerId, modelId, modification, volume, year],
  );
  const filterOptionsQuery = useBackofficeQuery<BackofficeAutoDbVehicleFilterOptions>(filterOptionsQueryFn, [
    year,
    manufacturerId,
    modelId,
    modification,
    volume,
  ]);
  const filterOptions = filterOptionsQuery.data;
  const manufacturers = filterOptions?.manufacturers ?? [];
  const models = filterOptions?.models ?? [];
  const modifications = filterOptions?.modifications ?? [];
  const volumes = filterOptions?.volumes ?? [];
  const engines = filterOptions?.engines ?? [];

  const vehiclesQueryFn = useCallback(
    (token: string) =>
      !manufacturerId || !modelId
        ? Promise.resolve({ count: 0, results: [] as BackofficeAutoDbVehicleRow[] })
        :
      getBackofficeAutoDbVehicles(token, {
        q: debouncedQ,
        manufacturer_id: manufacturerId,
        model_id: modelId,
        year,
        modification,
        volume,
        engine,
        page,
        page_size: pageSize,
      }),
    [debouncedQ, engine, manufacturerId, modelId, modification, page, pageSize, volume, year],
  );

  const { data, isLoading, error } = useBackofficeQuery<{ count: number; results: BackofficeAutoDbVehicleRow[] }>(vehiclesQueryFn, [
    debouncedQ,
    manufacturerId,
    modelId,
    year,
    modification,
    volume,
    engine,
    page,
    pageSize,
  ]);

  const rows = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const pagesCount = useMemo(() => Math.max(1, Math.ceil(totalCount / pageSize)), [pageSize, totalCount]);
  const readyForTable = isVehicleTableReady(manufacturerId, modelId);
  const emptyLabel = !manufacturerId
    ? t("states.selectMake")
    : !modelId
      ? t("states.selectModel")
      : t("empty");
  const filterFieldClassName = "h-10 rounded-md border px-3 text-sm";
  const filterFieldStyle = { borderColor: "var(--border)", backgroundColor: "var(--surface)" } as const;
  const disableSearchFilters = isHydrated && !readyForTable;
  const disableManufacturer = isHydrated && (!year || filterOptionsQuery.isLoading);
  const disableModel = isHydrated && (!year || isModelSelectorDisabled(manufacturerId) || filterOptionsQuery.isLoading);
  const disableModification = isHydrated && (!year || !manufacturerId || !modelId || filterOptionsQuery.isLoading);
  const disableVolume = isHydrated && (!year || !manufacturerId || !modelId || !modification || filterOptionsQuery.isLoading);
  const disableEngine = isHydrated && (!year || !manufacturerId || !modelId || !modification || !volume || filterOptionsQuery.isLoading);

  return (
    <section>
      <PageHeader title={t("title")} description={t("subtitle")} />

      <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4 2xl:grid-cols-8">
        <input
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(1);
          }}
          placeholder={t("search")}
          className={`${filterFieldClassName} min-w-0`}
          style={filterFieldStyle}
          disabled={disableSearchFilters}
        />

        <select
          value={year}
          onChange={(event) => {
            setYear(event.target.value);
            setManufacturerId("");
            setModelId("");
            setModification("");
            setVolume("");
            setEngine("");
            setPage(1);
          }}
          className={`${filterFieldClassName} min-w-0`}
          style={filterFieldStyle}
        >
          <option value="">{t("filters.allYears")}</option>
          {(filterOptions?.years ?? []).map((item) => (
            <option key={item} value={String(item)}>
              {item}
            </option>
          ))}
        </select>

        <select
          value={manufacturerId}
          onChange={(event) => {
            setManufacturerId(event.target.value);
            setModelId("");
            setModification("");
            setVolume("");
            setEngine("");
            setPage(1);
          }}
          className={`${filterFieldClassName} min-w-0`}
          style={filterFieldStyle}
          disabled={disableManufacturer}
        >
          <option value="">{filterOptionsQuery.isLoading ? tCommon("loading") : t("filters.selectMake")}</option>
          {manufacturers.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>

        <select
          value={modelId}
          onChange={(event) => {
            setModelId(event.target.value);
            setModification("");
            setVolume("");
            setEngine("");
            setPage(1);
          }}
          className={`${filterFieldClassName} min-w-0`}
          style={filterFieldStyle}
          disabled={disableModel}
        >
          <option value="">
            {filterOptionsQuery.isLoading && manufacturerId ? tCommon("loading") : t("filters.selectModel")}
          </option>
          {models.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>

        <select
          value={modification}
          onChange={(event) => {
            setModification(event.target.value);
            setVolume("");
            setEngine("");
            setPage(1);
          }}
          className={`${filterFieldClassName} min-w-0`}
          style={filterFieldStyle}
          disabled={disableModification}
        >
          <option value="">{t("filters.allModifications")}</option>
          {modifications.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          value={volume}
          onChange={(event) => {
            setVolume(event.target.value);
            setEngine("");
            setPage(1);
          }}
          className={`${filterFieldClassName} min-w-0`}
          style={filterFieldStyle}
          disabled={disableVolume}
        >
          <option value="">{t("filters.allCapacities")}</option>
          {volumes.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          value={engine}
          onChange={(event) => {
            setEngine(event.target.value);
            setPage(1);
          }}
          className={`${filterFieldClassName} min-w-0`}
          style={filterFieldStyle}
          disabled={disableEngine}
        >
          <option value="">{t("filters.allEngines")}</option>
          {engines.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        <select
          value={String(pageSize)}
          onChange={(event) => {
            const nextSize = Number(event.target.value) as (typeof PAGE_SIZE_OPTIONS)[number];
            setPageSize(nextSize);
            setPage(1);
          }}
          className={`${filterFieldClassName} min-w-0`}
          style={filterFieldStyle}
        >
          {PAGE_SIZE_OPTIONS.map((sizeOption) => (
            <option key={sizeOption} value={sizeOption}>
              {`${t("pagination.perPage")}: ${sizeOption}`}
            </option>
          ))}
        </select>
      </div>

      <AsyncState
        isLoading={readyForTable && isLoading}
        error={error || filterOptionsQuery.error}
        empty={!rows.length}
        emptyLabel={emptyLabel}
      >
        <BackofficeTable
          rows={rows}
          emptyLabel={emptyLabel}
          getRowKey={(item, rowIndex) => `${item.passanger_car_id}:${rowIndex}`}
          columns={[
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
              key: "period",
              label: t("table.columns.period"),
              render: (item) => asText(item.period),
            },
            {
              key: "volume",
              label: t("table.columns.capacity"),
              render: (item) => asText(item.volume),
            },
            {
              key: "engine",
              label: t("table.columns.engine"),
              render: (item) => asText(item.engine),
            },
            {
              key: "hp",
              label: t("table.columns.hp"),
              render: (item) => asText(item.hp),
            },
            {
              key: "kw",
              label: t("table.columns.kw"),
              render: (item) => asText(item.kw),
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
