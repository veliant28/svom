"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Timer } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  createAutoDbMatchingJobDryRun,
  getAutoDbMatchingRemoteQuota,
  manualAutoDbSearchLocal,
  manualAutoDbSearchRemote,
  planAutoDbCloneSync,
  auditAutoDbLink,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { AutoDbProductJob, AutoDbRemoteQuota, AutoDbSearchResult } from "@/features/backoffice/types/backoffice";

import {
  buttonClass,
  fieldClass,
  formatCountdown,
  MiniKpi,
  Panel,
  StatusPill,
  segmentedControlButtonClass,
  segmentedControlClass,
  surface2Style,
  surfaceStyle,
} from "./ui";

type SourceMode = "local" | "remote" | "both";

export function AutoDbMatchingSearchTab({ seedJob }: { seedJob: AutoDbProductJob | null }) {
  const t = useTranslations("backoffice.autodbMatching");
  const { showSuccess, showWarning, showApiError } = useBackofficeFeedback();
  const [supplierId, setSupplierId] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [article, setArticle] = useState("");
  const [source, setSource] = useState<SourceMode>("local");
  const [results, setResults] = useState<AutoDbSearchResult[]>([]);
  const [selected, setSelected] = useState<AutoDbSearchResult | null>(null);
  const quotaQuery = useQuotaQuery();

  useEffect(() => {
    if (!seedJob) return;
    setSupplierId(String(seedJob.autodb_supplier_id ?? ""));
    setSupplierName(seedJob.autodb_supplier_display || seedJob.raw_brand);
    setArticle(seedJob.canonical_article || seedJob.article_value);
  }, [seedJob]);

  const variants = useMemo(() => articleVariants(article), [article]);
  const quotaPaused = quotaQuery.data?.status === "quota_paused";

  const runSearch = useCallback(async () => {
    if (!quotaQuery.token || !article || !supplierId) {
      showWarning(t("toasts.validationError"));
      return;
    }
    if ((source === "remote" || source === "both") && quotaPaused) {
      showWarning(t("quota.remoteDisabled"));
      return;
    }
    try {
      const body = { supplier_id: supplierId, supplier_name: supplierName, brand: supplierName, article };
      const chunks: AutoDbSearchResult[] = [];
      if (source === "local" || source === "both") {
        showSuccess(t("toasts.localSearchStarted"));
        chunks.push(...(await manualAutoDbSearchLocal(quotaQuery.token, body)).results);
      }
      if (source === "remote" || source === "both") {
        showSuccess(t("toasts.remoteSearchStarted"));
        chunks.push(...(await manualAutoDbSearchRemote(quotaQuery.token, body)).results);
        await quotaQuery.refetch();
      }
      setResults(chunks);
      setSelected(chunks[0] ?? null);
      showSuccess(chunks.some((item) => item.status.includes("found")) ? t("toasts.localResultFound") : t("toasts.localResultNotFound"));
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    }
  }, [article, quotaPaused, quotaQuery, showApiError, showSuccess, showWarning, source, supplierId, supplierName, t]);

  const runResultAction = useCallback(async (kind: "job" | "clone" | "audit") => {
    if (!quotaQuery.token || !selected) return;
    try {
      const body = { supplier_id: selected.supplier_id, article: selected.matched_stored_article || article, result: selected };
      if (kind === "job") await createAutoDbMatchingJobDryRun(quotaQuery.token, body);
      if (kind === "clone") await planAutoDbCloneSync(quotaQuery.token, body);
      if (kind === "audit") await auditAutoDbLink(quotaQuery.token, body);
      showSuccess(kind === "clone" ? t("toasts.clonePlanGenerated") : t("toasts.dryRunCompleted"));
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    }
  }, [article, quotaQuery.token, selected, showApiError, showSuccess, t]);

  return (
    <div className="grid max-h-[calc(100vh-118px)] grid-cols-1 gap-3 overflow-hidden xl:grid-cols-[390px_minmax(0,1fr)]">
      <Panel className="grid content-start gap-3">
        <input className={fieldClass} style={surfaceStyle} value={supplierName} onChange={(event) => setSupplierName(event.target.value)} placeholder={t("search.supplier")} />
        <input className={fieldClass} style={surfaceStyle} value={supplierId} onChange={(event) => setSupplierId(event.target.value)} placeholder={t("search.supplierId")} />
        <input className={fieldClass} style={surfaceStyle} value={article} onChange={(event) => setArticle(event.target.value)} placeholder={t("search.article")} />
        <div className={`grid grid-cols-3 ${segmentedControlClass}`} style={surface2Style}>
          {(["local", "remote", "both"] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={segmentedControlButtonClass}
              style={{
                borderColor: source === item ? "#2563eb" : "var(--border)",
                backgroundColor: source === item ? "#2563eb" : "var(--surface-2)",
                color: source === item ? "#ffffff" : "var(--text)",
              }}
              onClick={() => setSource(item)}
            >
              {t(`search.sources.${item}` as never)}
            </button>
          ))}
        </div>
        <button type="button" className={buttonClass} style={surfaceStyle} disabled={(source !== "local" && quotaPaused) || !article || !supplierId} onClick={() => void runSearch()}>
          {source === "remote" ? t("actions.remoteSearch") : t("actions.localSearch")}
        </button>
        <QuotaSummary quota={quotaQuery.data} />
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em]" style={{ color: "var(--muted)" }}>{t("search.variants")}</p>
          <div className="flex flex-wrap gap-1">
            {variants.map((item) => <StatusPill key={item}>{item}</StatusPill>)}
          </div>
        </div>
      </Panel>

      <Panel className="grid min-h-0 gap-3">
        <AsyncState isLoading={false} error={null} empty={!results.length} emptyLabel={t("states.emptySearch")}>
          <div className="min-h-0 overflow-auto rounded-xl border" style={surfaceStyle}>
            <table className="min-w-[1160px] w-full border-collapse text-xs">
              <thead style={{ backgroundColor: "var(--surface-2)" }}>
                <tr>{["source", "supplier", "searched", "matched", "articleId", "prd", "attributes", "fitments", "images", "status"].map((key) => <th key={key} className="px-2 py-2 text-left">{t(`search.columns.${key}` as never)}</th>)}</tr>
              </thead>
              <tbody>
                {results.map((row, index) => (
                  <tr key={`${row.source}-${index}`} className="cursor-pointer border-t" style={{ borderColor: "var(--border)" }} onClick={() => setSelected(row)}>
                    <td className="px-2 py-2">{row.source}</td>
                    <td className="px-2 py-2">{row.supplier_id} / {row.supplier_name}</td>
                    <td className="px-2 py-2">{row.searched_article}</td>
                    <td className="px-2 py-2">{row.matched_stored_article || "-"}</td>
                    <td className="px-2 py-2">{row.article_id || row.article_key || "-"}</td>
                    <td className="px-2 py-2">{row.prd_linkage_present ? t("common.yes") : t("common.no")}</td>
                    <td className="px-2 py-2">{row.attributes_available_count}</td>
                    <td className="px-2 py-2">{row.fitments_available_count}</td>
                    <td className="px-2 py-2">{row.images_available_count}</td>
                    <td className="px-2 py-2">
                      <BackofficeStatusChip tone={row.status.includes("found") ? "success" : row.status === "quota_paused" ? "error" : "info"}>
                        {row.status}
                      </BackofficeStatusChip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ResultDetails result={selected} onAction={runResultAction} />
        </AsyncState>
      </Panel>
    </div>
  );
}

function useQuotaQuery() {
  const queryFn = useCallback((token: string) => getAutoDbMatchingRemoteQuota(token), []);
  const quotaQuery = useBackofficeQuery<AutoDbRemoteQuota>(queryFn);
  useEffect(() => {
    const intervalId = window.setInterval(() => void quotaQuery.refetch(), 15_000);
    return () => window.clearInterval(intervalId);
  }, [quotaQuery]);
  return quotaQuery;
}

function QuotaSummary({ quota }: { quota: AutoDbRemoteQuota | null }) {
  const t = useTranslations("backoffice.autodbMatching");
  return (
    <div className="grid gap-2">
      <div className="grid grid-cols-2 gap-2">
        <MiniKpi title={t("quota.used")} value={`${quota?.estimated_queries_used ?? 0} / ${quota?.estimated_limit_per_hour ?? 10000}`} />
        <MiniKpi title={t("quota.resetIn")} value={formatCountdown(quota?.seconds_until_reset ?? 0)} />
      </div>
      <BackofficeStatusChip tone="info" icon={Timer} palette="countdown">
        {t("quota.resetIn")}: {formatCountdown(quota?.seconds_until_reset ?? 0)}
      </BackofficeStatusChip>
    </div>
  );
}

function ResultDetails({ result, onAction }: { result: AutoDbSearchResult | null; onAction: (kind: "job" | "clone" | "audit") => void }) {
  const t = useTranslations("backoffice.autodbMatching");
  if (!result) return null;
  return (
    <div className="grid gap-2 rounded-xl border p-3 text-xs" style={surfaceStyle}>
      <div className="flex flex-wrap gap-2">
        <button className={buttonClass} style={surfaceStyle} onClick={() => onAction("job")}>{t("actions.createJob")}</button>
        <button className={buttonClass} style={surfaceStyle} onClick={() => onAction("clone")}>{t("actions.clonePlan")}</button>
        <button className={buttonClass} style={surfaceStyle} onClick={() => onAction("audit")}>{t("actions.audit")}</button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {["article_key", "matched_table", "source_path", "confidence", "reason"].map((key) => (
          <div key={key}><span style={{ color: "var(--muted)" }}>{key}: </span><span className="font-semibold">{String(result[key as keyof AutoDbSearchResult] ?? "-")}</span></div>
        ))}
      </div>
    </div>
  );
}

function articleVariants(value: string): string[] {
  const raw = value.trim();
  const upper = raw.toUpperCase();
  const collapsed = upper.replace(/\s+/g, " ");
  const canonical = upper.replace(/[^A-Z0-9]/g, "");
  const alphaDigit = canonical.replace(/^([A-Z]+)(\d+)$/, "$1 $2");
  return Array.from(new Set([raw, upper, collapsed, canonical, alphaDigit, alphaDigit.replace(" ", "-")].filter(Boolean)));
}
