"use client";

import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

import {
  auditAutoDbLink,
  createAutoDbMatchingJobDryRun,
  getAutoDbMatchingJobs,
  runAutoDbLocalDryRun,
} from "@/features/backoffice/api/backoffice-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { AutoDbJobsResponse, AutoDbProductJob } from "@/features/backoffice/types/backoffice";

import { AutoDbEvidenceDrawer } from "./evidence-drawer";
import { buttonClass, buttonCompactClass, fieldClass, StatusPill, surfaceStyle } from "./ui";

const PAGE_SIZES = [15, 25, 50, 100] as const;
const STATUS_FLAGS = ["only_safe_candidates", "needs_review", "quota_paused", "bad_article_source", "split_needed", "unsafe_ambiguous"];

export function AutoDbMatchingProductsTab({ onSearchProduct }: { onSearchProduct: (job: AutoDbProductJob) => void }) {
  const t = useTranslations("backoffice.autodbMatching");
  const { showSuccess, showApiError, showInfo } = useBackofficeFeedback();
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({ tecdoc_status: "" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZES)[number]>(25);
  const [ordering, setOrdering] = useState("-updated_at");
  const [selected, setSelected] = useState<string[]>([]);
  const [drawerJobId, setDrawerJobId] = useState<string | null>(null);

  const params = useMemo(() => ({ q: query, page, page_size: pageSize, ordering, ...filters }), [filters, ordering, page, pageSize, query]);
  const queryFn = useCallback((token: string) => getAutoDbMatchingJobs(token, params), [params]);
  const { token, data, isLoading, error, refetch } = useBackofficeQuery<AutoDbJobsResponse>(queryFn, [params]);
  const rows = useMemo(() => data?.results ?? [], [data?.results]);
  const totalPages = Math.max(1, Math.ceil((data?.count ?? 0) / pageSize));

  const runRowAction = useCallback(async (job: AutoDbProductJob, action: "create" | "local" | "audit") => {
    if (!token) return;
    try {
      const body = { job_ids: [job.id], product_id: job.product.id, supplier_id: job.autodb_supplier_id, article: job.canonical_article };
      if (action === "create") await createAutoDbMatchingJobDryRun(token, body);
      if (action === "local") await runAutoDbLocalDryRun(token, body);
      if (action === "audit") await auditAutoDbLink(token, body);
      showSuccess(t(action === "create" ? "toasts.jobCreated" : "toasts.dryRunCompleted"));
      await refetch();
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    }
  }, [refetch, showApiError, showSuccess, t, token]);

  const exportRows = useCallback(() => {
    const csv = ["sku,name,brand,status,canonical_article", ...rows.map((row) => [
      row.product.sku,
      row.product.name,
      row.raw_brand,
      row.matching_status,
      row.canonical_article,
    ].map((item) => `"${String(item).replaceAll('"', '""')}"`).join(","))].join("\n");
    void navigator.clipboard?.writeText(csv);
    showInfo(t("toasts.exportDownloaded"));
  }, [rows, showInfo, t]);

  return (
    <>
      <div className="grid max-h-[calc(100vh-118px)] gap-3 overflow-hidden">
        <Filters
          query={query}
          filters={filters}
          pageSize={pageSize}
          onQuery={setQuery}
          onFilters={(next) => { setFilters(next); setPage(1); }}
          onPageSize={(size) => { setPageSize(size); setPage(1); }}
          onExport={exportRows}
        />
        <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("states.emptyProducts")}>
          <div className="min-h-0 overflow-auto rounded-xl border" style={surfaceStyle}>
            <table className="min-w-[1680px] w-full border-collapse text-xs">
              <thead style={{ backgroundColor: "var(--surface-2)" }}>
                <tr>
                  <Th><input type="checkbox" checked={selected.length === rows.length && rows.length > 0} onChange={(event) => setSelected(event.target.checked ? rows.map((row) => row.id) : [])} /></Th>
                  {["sku", "name", "brand", "autodb", "supplier_code", "article_source", "article_value", "canonical", "price_stock", "price", "tecdoc", "status", "recommended", "reason", "actions"].map((key) => (
                    <Th key={key} onClick={() => ["sku", "name", "status"].includes(key) && setOrdering(ordering === key ? `-${key}` : key)}>
                      {t(`products.columns.${key}` as never)}
                    </Th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                    <Td><input type="checkbox" checked={selected.includes(row.id)} onChange={(event) => setSelected((prev) => event.target.checked ? [...prev, row.id] : prev.filter((id) => id !== row.id))} /></Td>
                    <Td>{row.product.svom_sku || row.product.sku}</Td>
                    <Td><span className="font-semibold">{row.product.name}</span></Td>
                    <Td>{row.raw_brand || row.product.brand}</Td>
                    <Td>{row.autodb_supplier_display || row.autodb_supplier_id || "-"}</Td>
                    <Td>{row.supplier_code || "-"}</Td>
                    <Td>{row.article_source || "-"}</Td>
                    <Td>{row.article_value || "-"}</Td>
                    <Td>{row.canonical_article || "-"}</Td>
                    <Td>{row.stock_qty} / {row.currency || "-"}</Td>
                    <Td>{row.has_product_price ? t("common.yes") : t("common.no")}</Td>
                    <Td>{row.tecdoc_status}</Td>
                    <Td><StatusPill tone={row.matching_status === "safe_link_candidate" ? "ok" : row.matching_status === "quota_paused" ? "danger" : "neutral"}>{row.matching_status}</StatusPill></Td>
                    <Td>{row.recommended_action}</Td>
                    <Td>{row.last_evidence.reason || "-"}</Td>
                    <Td>
                      <div className="flex flex-wrap gap-1">
                        <button className={buttonCompactClass} style={surfaceStyle} onClick={() => setDrawerJobId(row.id)}>{t("actions.details")}</button>
                        <button className={buttonCompactClass} style={surfaceStyle} onClick={() => void runRowAction(row, "create")}>{t("actions.createJob")}</button>
                        <button className={buttonCompactClass} style={surfaceStyle} onClick={() => void runRowAction(row, "local")}>{t("actions.localDryRun")}</button>
                        <button className={buttonCompactClass} style={surfaceStyle} onClick={() => onSearchProduct(row)}>{t("actions.manualSearch")}</button>
                        <button className={buttonCompactClass} style={surfaceStyle} onClick={() => void runRowAction(row, "audit")}>{t("actions.audit")}</button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
            <span>{t("products.pagination.total", { count: data?.count ?? 0 })}</span>
            <div className="flex items-center gap-2">
              <button className={buttonClass} style={surfaceStyle} disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>{t("common.prev")}</button>
              <span>{page} / {totalPages}</span>
              <button className={buttonClass} style={surfaceStyle} disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>{t("common.next")}</button>
            </div>
          </div>
        </AsyncState>
      </div>
      <AutoDbEvidenceDrawer jobId={drawerJobId} onClose={() => setDrawerJobId(null)} />
    </>
  );
}

function Filters({ query, filters, pageSize, onQuery, onFilters, onPageSize, onExport }: {
  query: string;
  filters: Record<string, string>;
  pageSize: number;
  onQuery: (value: string) => void;
  onFilters: (value: Record<string, string>) => void;
  onPageSize: (value: 15 | 25 | 50 | 100) => void;
  onExport: () => void;
}) {
  const t = useTranslations("backoffice.autodbMatching");
  const setFilter = (key: string, value: string) => onFilters({ ...filters, [key]: value });
  return (
    <div className="grid gap-2">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-6">
        <input className={fieldClass} style={surfaceStyle} value={query} onChange={(event) => onQuery(event.target.value)} placeholder={t("products.search")} />
        {["supplier_code", "brand", "autodb_supplier", "matching_status", "article_source"].map((key) => (
          <input key={key} className={fieldClass} style={surfaceStyle} value={filters[key] ?? ""} onChange={(event) => setFilter(key, event.target.value)} placeholder={t(`filters.${key}` as never)} />
        ))}
        <select className={fieldClass} style={surfaceStyle} value={filters.tecdoc_status ?? ""} onChange={(event) => setFilter("tecdoc_status", event.target.value)}>
          <option value="">{t("filters.all")}</option>
          <option value="tecdoc">{t("filters.tecdocOnly")}</option>
          <option value="non_tecdoc">{t("filters.nonTecdocOnly")}</option>
          <option value="unknown">{t("filters.unknownReview")}</option>
        </select>
        <select className={fieldClass} style={surfaceStyle} value={String(pageSize)} onChange={(event) => onPageSize(Number(event.target.value) as 15 | 25 | 50 | 100)}>
          {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
        </select>
        <button type="button" className={buttonClass} style={surfaceStyle} onClick={onExport}>{t("actions.export")}</button>
      </div>
      <div className="flex flex-wrap gap-2">
        {STATUS_FLAGS.map((key) => (
          <label key={key} className="inline-flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-semibold" style={surfaceStyle}>
            <input type="checkbox" checked={filters[key] === "true"} onChange={(event) => setFilter(key, event.target.checked ? "true" : "")} />
            {t(`filters.${key}` as never)}
          </label>
        ))}
      </div>
    </div>
  );
}

function Th({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return <th className="px-2 py-2 text-left font-semibold uppercase tracking-wide" onClick={onClick}>{children}</th>;
}

function Td({ children }: { children: ReactNode }) {
  return <td className="px-2 py-2 align-top">{children}</td>;
}
