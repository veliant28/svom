"use client";

import { CheckCircle2, Link2, Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { useTranslations } from "next-intl";
import Image from "next/image";

import {
  createAutoDbMatchingJobDryRun,
  getAutoDbMatchingRemoteQuota,
  lookupAutoDbMatchingProducts,
  manualAutoDbSearchLocal,
  manualAutoDbSearchRemote,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type {
  AutoDbProductJob,
  AutoDbRemoteQuota,
  AutoDbSearchResult,
  AutoDbSkuLookupRow,
} from "@/features/backoffice/types/backoffice";

import {
  fieldClass,
  Panel,
  surfaceStyle,
} from "./ui";

type SourceMode = "local" | "remote" | "both";
type SearchCandidate = {
  supplier_id: number;
  supplier_name: string;
  matched_stored_article: string;
  hits: number;
  matched_table: string;
};
type CompatibilityRow = {
  id?: string | number;
  make?: string;
  model?: string;
  label?: string;
  modification?: string;
  engine?: string;
  generation?: string;
};

export function AutoDbMatchingSearchTab({
  seedJob,
  refreshNonce,
}: {
  seedJob: AutoDbProductJob | null;
  refreshNonce: number;
}) {
  const t = useTranslations("backoffice.autodbMatching");
  const { showSuccess, showWarning, showApiError } = useBackofficeFeedback();
  const [article, setArticle] = useState("");
  const [source, setSource] = useState<SourceMode>("local");
  const [candidates, setCandidates] = useState<SearchCandidate[]>([]);
  const [selectedCandidateKey, setSelectedCandidateKey] = useState("");
  const [result, setResult] = useState<AutoDbSearchResult | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [selectedMake, setSelectedMake] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [skuQuery, setSkuQuery] = useState("");
  const [skuResults, setSkuResults] = useState<AutoDbSkuLookupRow[]>([]);
  const [selectedSku, setSelectedSku] = useState<AutoDbSkuLookupRow | null>(null);
  const [isSkuLookupLoading, setIsSkuLookupLoading] = useState(false);
  const [isBindLoading, setIsBindLoading] = useState(false);
  const [isSkuDropdownOpen, setIsSkuDropdownOpen] = useState(false);
  const [skuActiveIndex, setSkuActiveIndex] = useState(-1);
  const skuInputRef = useRef<HTMLInputElement | null>(null);
  const handledRefreshNonceRef = useRef(0);
  const quotaQuery = useQuotaQuery();

  useEffect(() => {
    if (!seedJob) return;
    setArticle(seedJob.canonical_article || seedJob.article_value || "");
  }, [seedJob]);

  useEffect(() => {
    setSelectedMake("");
    setSelectedModel("");
    setSkuQuery("");
    setSkuResults([]);
    setSelectedSku(null);
    setIsSkuDropdownOpen(false);
    setSkuActiveIndex(-1);
  }, [result?.article_key, result?.matched_stored_article, result?.supplier_id]);

  const quotaPaused = quotaQuery.data?.status === "quota_paused";

  const loadCandidateDetails = useCallback(async (candidate: SearchCandidate) => {
    if (!quotaQuery.token) return;
    if ((source === "remote" || source === "both") && quotaPaused) {
      showWarning(t("quota.remoteDisabled"));
      return;
    }
    setSelectedCandidateKey(candidateKey(candidate));
    setIsLoadingDetails(true);
    try {
      const body = {
        supplier_id: candidate.supplier_id,
        supplier_name: candidate.supplier_name,
        brand: candidate.supplier_name,
        article,
      };
      const details: AutoDbSearchResult[] = [];
      let hasLocalRows = false;
      if (source === "local" || source === "both") {
        const localResponse = await manualAutoDbSearchLocal(quotaQuery.token, body);
        const localRows = localResponse.results ?? [];
        if (localRows.length > 0) {
          hasLocalRows = true;
          details.push(...localRows);
        }
      }
      if (source === "remote" || source === "both") {
        try {
          const remoteResponse = await manualAutoDbSearchRemote(quotaQuery.token, body);
          details.push(...(remoteResponse.results ?? []));
          await quotaQuery.refetch();
        } catch (err) {
          if (!hasLocalRows) {
            throw err;
          }
          showWarning(t("toasts.apiError"));
        }
      }
      const first = details
        .slice()
        .sort((a, b) => scoreSearchResult(b) - scoreSearchResult(a))[0] ?? null;
      setResult(first);
      const foundStatus = first?.status.endsWith("_found") && first.status !== "not_found";
      if (foundStatus) {
        showSuccess(t("toasts.localResultFound"));
      } else {
        showWarning(t("toasts.localResultNotFound"));
      }
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    } finally {
      setIsLoadingDetails(false);
    }
  }, [article, quotaPaused, quotaQuery, showApiError, showSuccess, showWarning, source, t]);

  const findCandidates = useCallback(async () => {
    if (!quotaQuery.token || !article.trim()) {
      showWarning(t("toasts.validationArticleRequired"));
      return;
    }
    try {
      const response = await manualAutoDbSearchLocal(quotaQuery.token, { article });
      const rows = response.candidates ?? [];
      setCandidates(rows);
      setResult(null);
      if (!rows.length) {
        setSelectedCandidateKey("");
        showWarning(t("toasts.localResultNotFound"));
        return;
      }
      setSelectedCandidateKey(candidateKey(rows[0]));
      showSuccess(t("toasts.candidatesFound", { count: rows.length }));
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    }
  }, [
    article,
    quotaQuery.token,
    showApiError,
    showSuccess,
    showWarning,
    t,
  ]);

  useEffect(() => {
    const value = skuQuery.trim();
    if (!quotaQuery.token || value.length < 2) {
      setSkuResults([]);
      setIsSkuLookupLoading(false);
      setSkuActiveIndex(-1);
      return;
    }
    let cancelled = false;
    setIsSkuLookupLoading(true);
    const timeoutId = window.setTimeout(async () => {
      try {
        const response = await lookupAutoDbMatchingProducts(quotaQuery.token as string, { q: value, limit: 8 });
        if (cancelled) return;
        const rows = response.results ?? [];
        setSkuResults(rows);
        setSkuActiveIndex(rows.length ? 0 : -1);
        setIsSkuDropdownOpen(true);
      } catch (err) {
        if (!cancelled) {
          setSkuResults([]);
          setSkuActiveIndex(-1);
          showApiError(err, t("toasts.apiError"));
        }
      } finally {
        if (!cancelled) setIsSkuLookupLoading(false);
      }
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [quotaQuery.token, showApiError, skuQuery, t]);

  const applySkuSelection = useCallback((row: AutoDbSkuLookupRow) => {
    setSelectedSku(row);
    setSkuQuery(row.svom_sku || row.sku || "");
    setIsSkuDropdownOpen(false);
  }, []);

  const runManualBind = useCallback(async () => {
    if (!quotaQuery.token || !result) return;
    if (!selectedSku) {
      showWarning(t("toasts.selectSkuRequired"));
      return;
    }
    if (!result.supplier_id || !result.matched_stored_article) {
      showWarning(t("toasts.selectResultRequired"));
      return;
    }
    setIsBindLoading(true);
    try {
      const response = await createAutoDbMatchingJobDryRun(quotaQuery.token, {
        product_id: selectedSku.id,
        supplier_id: result.supplier_id,
        supplier_name: result.supplier_name,
        article: result.matched_stored_article,
        article_id: result.article_id ? Number(result.article_id) : undefined,
        dispatch_async: true,
      });
      if (response.status === "queued" || response.mode === "async") {
        showSuccess(t("toasts.manualBindQueued"));
      } else if (response.status === "bound" || response.status === "done") {
        showSuccess(t("toasts.manualBindDone"));
      } else {
        showSuccess(t("toasts.manualBindQueued"));
      }
    } catch (err) {
      showApiError(err, t("toasts.apiError"));
    } finally {
      setIsBindLoading(false);
    }
  }, [quotaQuery.token, result, selectedSku, showApiError, showSuccess, showWarning, t]);

  useEffect(() => {
    if (refreshNonce <= 0 || handledRefreshNonceRef.current === refreshNonce) return;
    handledRefreshNonceRef.current = refreshNonce;
    void quotaQuery.refetch();
    const currentCandidate = candidates.find((item) => candidateKey(item) === selectedCandidateKey);
    if (currentCandidate) {
      void loadCandidateDetails(currentCandidate);
      return;
    }
    if (article.trim()) {
      void findCandidates();
    }
  }, [article, candidates, findCandidates, loadCandidateDetails, quotaQuery, refreshNonce, selectedCandidateKey]);

  return (
    <div className="grid h-[calc(100vh-11rem)] min-h-[560px] grid-cols-1 gap-3 overflow-hidden xl:grid-cols-[minmax(0,1.45fr)_560px]">
      <Panel className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3">
        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2">
          <div className="inline-flex items-center gap-1 rounded-xl border p-1" style={surfaceStyle}>
            {([
              { key: "local", short: "Л", title: t("search.sources.local"), activeBg: "#15803d", activeColor: "#ffffff", idleBg: "#dcfce7", idleColor: "#166534", idleBorder: "#86efac" },
              { key: "remote", short: "У", title: t("search.sources.remote"), activeBg: "#c2410c", activeColor: "#ffffff", idleBg: "#ffedd5", idleColor: "#9a3412", idleBorder: "#fdba74" },
              { key: "both", short: "2", title: t("search.sources.both"), activeBg: "#b91c1c", activeColor: "#ffffff", idleBg: "#fee2e2", idleColor: "#991b1b", idleBorder: "#fca5a5" },
            ] as const).map((item) => {
              const active = source === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  title={item.title}
                  aria-label={item.title}
                  className="inline-flex h-10 min-w-10 items-center justify-center rounded-lg border px-2 text-sm font-bold transition-colors"
                  style={{
                    borderColor: active ? item.activeBg : item.idleBorder,
                    backgroundColor: active ? item.activeBg : item.idleBg,
                    color: active ? item.activeColor : item.idleColor,
                  }}
                  onClick={() => setSource(item.key)}
                >
                  {item.short}
                </button>
              );
            })}
          </div>

          <div className="relative min-w-0">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
            <input
              className={`${fieldClass} w-full pl-9`}
              style={surfaceStyle}
              value={article}
              onChange={(event) => setArticle(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void findCandidates();
                }
              }}
              placeholder={t("search.article")}
            />
          </div>

          <BackofficeTooltip content={t("actions.findByArticle")} placement="top" align="center" wrapperClassName="inline-flex">
            <button
              type="button"
              aria-label={t("actions.findByArticle")}
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border transition-colors disabled:cursor-not-allowed disabled:opacity-60"
              style={surfaceStyle}
              disabled={!article.trim()}
              onClick={() => void findCandidates()}
            >
              <Search size={17} />
            </button>
          </BackofficeTooltip>
        </div>

        <div className="min-h-0 overflow-auto rounded-xl border" style={surfaceStyle}>
          <table className="w-full border-collapse text-xs">
            <thead style={{ backgroundColor: "var(--surface-2)" }}>
              <tr className="border-b" style={{ borderColor: "var(--border)" }}>
                <th className="px-2 py-2 text-left">{t("search.matchesColumns.brand")}</th>
                <th className="px-2 py-2 text-left">{t("search.matchesColumns.article")}</th>
                <th className="w-[72px] px-2 py-2 text-center">{t("search.matchesColumns.status")}</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => {
                const key = candidateKey(candidate);
                const active = key === selectedCandidateKey;
                return (
                  <tr
                    key={key}
                    className="cursor-pointer border-b"
                    style={{ borderColor: "var(--border)", backgroundColor: active ? "var(--surface-2)" : "transparent" }}
                    onClick={() => void loadCandidateDetails(candidate)}
                  >
                    <td className="px-2 py-2"><BackofficeStatusChip tone={active ? "black" : "gray"}>{candidate.supplier_name}</BackofficeStatusChip></td>
                    <td className="px-2 py-2 font-semibold">{candidate.matched_stored_article}</td>
                    <td className="px-2 py-2 text-center">
                      <BackofficeStatusChip
                        tone="success"
                        icon={CheckCircle2}
                        className="h-6 w-6 justify-center gap-0 px-0 py-0 [&>span:last-child]:hidden"
                      >
                        {t("search.statusFound")}
                      </BackofficeStatusChip>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel className="grid h-full min-h-0">
        <AsyncState isLoading={isLoadingDetails} error={null} empty={!result} emptyLabel={t("states.emptySearch")}>
          {result ? (
            <ResultDetails
              result={result}
              selectedMake={selectedMake}
              selectedModel={selectedModel}
              onSelectedMake={setSelectedMake}
              onSelectedModel={setSelectedModel}
              skuQuery={skuQuery}
              skuResults={skuResults}
              selectedSku={selectedSku}
              isSkuLookupLoading={isSkuLookupLoading}
              isBindLoading={isBindLoading}
              isSkuDropdownOpen={isSkuDropdownOpen}
              skuActiveIndex={skuActiveIndex}
              skuInputRef={skuInputRef}
              onSkuQueryChange={setSkuQuery}
              onSkuDropdownOpen={setIsSkuDropdownOpen}
              onSkuActiveIndexChange={setSkuActiveIndex}
              onSkuSelect={applySkuSelection}
              onBind={runManualBind}
            />
          ) : null}
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

function ResultDetails({
  result,
  selectedMake,
  selectedModel,
  onSelectedMake,
  onSelectedModel,
  skuQuery,
  skuResults,
  selectedSku,
  isSkuLookupLoading,
  isBindLoading,
  isSkuDropdownOpen,
  skuActiveIndex,
  skuInputRef,
  onSkuQueryChange,
  onSkuDropdownOpen,
  onSkuActiveIndexChange,
  onSkuSelect,
  onBind,
}: {
  result: AutoDbSearchResult;
  selectedMake: string;
  selectedModel: string;
  onSelectedMake: (value: string) => void;
  onSelectedModel: (value: string) => void;
  skuQuery: string;
  skuResults: AutoDbSkuLookupRow[];
  selectedSku: AutoDbSkuLookupRow | null;
  isSkuLookupLoading: boolean;
  isBindLoading: boolean;
  isSkuDropdownOpen: boolean;
  skuActiveIndex: number;
  skuInputRef: RefObject<HTMLInputElement | null>;
  onSkuQueryChange: (value: string) => void;
  onSkuDropdownOpen: (value: boolean) => void;
  onSkuActiveIndexChange: (value: number) => void;
  onSkuSelect: (row: AutoDbSkuLookupRow) => void;
  onBind: () => Promise<void>;
}) {
  const t = useTranslations("backoffice.autodbMatching");
  const details = (result.details ?? {}) as Record<string, unknown>;
  const articleRow = isRecord(details.article) ? details.article : {};
  const attributePreviewRows = Array.isArray(details.attributes_preview)
    ? details.attributes_preview.filter((item): item is Record<string, unknown> => isRecord(item))
    : [];
  const compatibility = Array.isArray(details.compatibility_preview)
    ? details.compatibility_preview.filter((item): item is CompatibilityRow => isRecord(item))
    : [];

  const brandArticleLine = [result.supplier_name || "-", result.matched_stored_article || result.searched_article || "-"]
    .filter(Boolean)
    .join(" · ");
  const productName = resolveProductName(articleRow, result);
  const productDescription = resolveArticleDescription(articleRow, productName);

  const attributes = attributePreviewRows.length
    ? attributePreviewRows
        .map((item) => ({
          name: readString(item, "name") || readString(item, "description") || "-",
          value: readString(item, "value") || readString(item, "displayvalue") || "-",
        }))
        .slice(0, 24)
    : [];

  const imageUrls = Array.isArray(result.image_thumbnails) ? result.image_thumbnails.filter(Boolean) : [];
  const [activeImageIndex, setActiveImageIndex] = useState(0);

  useEffect(() => {
    setActiveImageIndex(0);
  }, [result.article_key, result.matched_stored_article, result.searched_article]);
  const makes = Array.from(new Set(compatibility.map((item) => (item.make || "").trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b));
  const models = Array.from(
    new Set(
      compatibility
        .filter((item) => !selectedMake || (item.make || "").trim() === selectedMake)
        .map((item) => (item.model || "").trim())
        .filter(Boolean),
    ),
  ).sort((a, b) => a.localeCompare(b));
  const visibleFitments = compatibility.filter((item) => {
    const make = (item.make || "").trim();
    const model = (item.model || "").trim();
    if (selectedMake && make !== selectedMake) return false;
    if (selectedModel && model !== selectedModel) return false;
    return true;
  });
  const totalFitmentsCount = Math.max(Number(result.fitments_available_count || 0), compatibility.length);

  return (
    <div className="grid min-h-0 auto-rows-min content-start gap-2 overflow-auto">
      <div className="pt-0.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold">{productName}</h3>
            <p className="mt-1 truncate text-sm" style={{ color: "var(--muted)" }}>
              {brandArticleLine}
              {productDescription ? ` · ${productDescription}` : ""}
            </p>
          </div>

          <div className="relative flex shrink-0 items-center gap-2">
            <div className="relative">
              <input
                ref={skuInputRef}
                value={skuQuery}
                onChange={(event) => {
                  onSkuQueryChange(event.target.value.toUpperCase().slice(0, 12));
                  onSkuDropdownOpen(true);
                }}
                onFocus={() => onSkuDropdownOpen(true)}
                onBlur={() => {
                  window.setTimeout(() => onSkuDropdownOpen(false), 120);
                }}
                onKeyDown={(event) => {
                  if (!isSkuDropdownOpen || !skuResults.length) {
                    if (event.key === "Enter" && selectedSku) {
                      event.preventDefault();
                      void onBind();
                    }
                    return;
                  }
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    onSkuActiveIndexChange(Math.min(skuActiveIndex + 1, skuResults.length - 1));
                    return;
                  }
                  if (event.key === "ArrowUp") {
                    event.preventDefault();
                    onSkuActiveIndexChange(Math.max(skuActiveIndex - 1, 0));
                    return;
                  }
                  if (event.key === "Enter") {
                    event.preventDefault();
                    const row = skuResults[Math.max(skuActiveIndex, 0)];
                    if (row) onSkuSelect(row);
                    return;
                  }
                  if (event.key === "Escape") {
                    onSkuDropdownOpen(false);
                  }
                }}
                className={`${fieldClass} w-[18ch] min-w-[18ch]`}
                style={surfaceStyle}
                maxLength={12}
                placeholder={t("search.skuPlaceholder")}
                aria-label={t("search.skuPlaceholder")}
              />
              {isSkuDropdownOpen ? (
                <div
                  className="absolute right-0 top-[calc(100%+6px)] z-20 w-[360px] overflow-hidden rounded-lg border shadow-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                >
                  {isSkuLookupLoading ? (
                    <p className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>{t("search.lookupLoading")}</p>
                  ) : skuResults.length ? (
                    <ul className="max-h-64 overflow-auto py-1">
                      {skuResults.map((row, index) => {
                        const isActive = index === skuActiveIndex;
                        const isSelected = selectedSku?.id === row.id;
                        return (
                          <li key={row.id}>
                            <button
                              type="button"
                              className="block w-full cursor-pointer px-3 py-2 text-left text-xs"
                              style={{
                                backgroundColor: isActive ? "var(--surface-2)" : "transparent",
                                color: "var(--text)",
                              }}
                              onMouseDown={(event) => {
                                event.preventDefault();
                                onSkuSelect(row);
                              }}
                            >
                              <p className="font-semibold">
                                {row.svom_sku || row.sku}
                                {isSelected ? ` · ${t("search.selectedSkuSuffix")}` : ""}
                              </p>
                              <p className="truncate" style={{ color: "var(--muted)" }}>
                                {row.brand_name} · {row.name}
                              </p>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="px-3 py-2 text-xs" style={{ color: "var(--muted)" }}>{t("search.lookupEmpty")}</p>
                  )}
                </div>
              ) : null}
            </div>

            <BackofficeTooltip content={t("actions.bindSkuTooltip")} placement="top" align="end" wrapperClassName="inline-flex">
              <button
                type="button"
                className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-60"
                style={surfaceStyle}
                onClick={() => void onBind()}
                disabled={!selectedSku || isBindLoading}
                aria-label={t("actions.bindSkuTooltip")}
              >
                <Link2 size={17} />
              </button>
            </BackofficeTooltip>
          </div>
        </div>
      </div>

      <section className="rounded-xl border p-2" style={surfaceStyle}>
        {imageUrls.length && activeImageIndex < imageUrls.length ? (
          <div className="relative h-56 w-full overflow-hidden rounded-lg border bg-white" style={{ borderColor: "var(--border)" }}>
            <Image
              src={imageUrls[activeImageIndex]}
              alt={brandArticleLine || "Auto_DB"}
              fill
              unoptimized
              sizes="(max-width: 1280px) 100vw, 560px"
              className="object-contain"
              onError={() => setActiveImageIndex((value) => value + 1)}
            />
          </div>
        ) : (
          <div
            className="flex h-56 w-full items-center justify-center rounded-lg border text-sm"
            style={{ borderColor: "var(--border)", color: "var(--muted)", backgroundColor: "var(--surface-2)" }}
          >
            {t("search.noImage")}
          </div>
        )}
      </section>

      <section className="rounded-xl border p-2" style={surfaceStyle}>
        <h3 className="mb-2 text-sm font-semibold">{t("search.attributesTitle")}</h3>
        {attributes.length ? (
          <ul className="space-y-1 text-sm" style={{ color: "var(--muted)" }}>
            {attributes.map((item) => (
              <li key={`${item.name}-${item.value}`}><span className="font-medium" style={{ color: "var(--text)" }}>{item.name}</span>: {item.value}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm" style={{ color: "var(--muted)" }}>{t("states.empty")}</p>
        )}
      </section>

      <section className="rounded-xl border p-2" style={surfaceStyle}>
        <h3 className="mb-2 text-sm font-semibold">{t("search.fitmentTitle")}</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs">
            {t("search.fitmentMakeLabel")}
            <select
              value={selectedMake}
              onChange={(event) => {
                onSelectedMake(event.target.value || "");
                onSelectedModel("");
              }}
              className="h-9 rounded-md border px-2 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <option value="">{t("search.fitmentAllMakes")}</option>
              {makes.map((make) => <option key={make} value={make}>{make}</option>)}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs">
            {t("search.fitmentModelLabel")}
            <select
              value={selectedModel}
              onChange={(event) => onSelectedModel(event.target.value || "")}
              className="h-9 rounded-md border px-2 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <option value="">{t("search.fitmentAllModels")}</option>
              {models.map((model) => <option key={model} value={model}>{model}</option>)}
            </select>
          </label>
        </div>

        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          {t("search.fitmentRows", { count: totalFitmentsCount })}
        </p>

        {visibleFitments.length ? (
          <div className="mt-2 max-h-56 space-y-1 overflow-auto pr-1">
            {visibleFitments.map((fitment, index) => (
              <div key={String(fitment.id ?? index)} className="rounded-md border px-2 py-1.5 text-xs" style={{ borderColor: "var(--border)", color: "var(--muted)" }}>
                <p className="font-medium" style={{ color: "var(--text)" }}>
                  {fitment.label || [fitment.make, fitment.model].filter(Boolean).join(" · ")}
                </p>
                <p>{[fitment.modification, fitment.engine, fitment.generation].filter(Boolean).join(" · ")}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>{t("search.fitmentEmpty")}</p>
        )}
      </section>
    </div>
  );
}

function candidateKey(candidate: SearchCandidate): string {
  return `${candidate.supplier_id}:${candidate.matched_stored_article}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readString(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value.trim() : "";
}


function resolveProductName(articleRow: Record<string, unknown>, result: AutoDbSearchResult): string {
  const keys = [
    "articleName",
    "ArticleName",
    "NormalizedDescription",
    "normalizedDescription",
    "normalizeddescription",
    "Description",
    "description",
    "displayName",
    "DisplayName",
    "name",
    "Name",
  ];
  for (const key of keys) {
    const value = articleRow[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  const fallback = String(result.generic || "").trim();
  return fallback || "-";
}

function resolveArticleDescription(articleRow: Record<string, unknown>, productName: string): string {
  const keys = [
    "Description",
    "description",
    "articleDescription",
    "ArticleDescription",
  ];
  const nameNorm = String(productName || "").trim().toLocaleLowerCase();
  for (const key of keys) {
    const value = articleRow[key];
    if (typeof value !== "string") continue;
    const text = value.trim();
    if (!text) continue;
    if (text.toLocaleLowerCase() === nameNorm) continue;
    return text;
  }
  return "";
}
function scoreSearchResult(result: AutoDbSearchResult): number {
  const statusScore = result.status.includes("found") ? 50 : 0;
  const linkageScore = result.prd_linkage_present ? 30 : 0;
  const attributesScore = Number(result.attributes_available_count || 0);
  const fitmentScore = Math.min(Number(result.fitments_available_count || 0), 40);
  const imageScore = Number(result.images_available_count || 0) * 2;
  return statusScore + linkageScore + attributesScore + fitmentScore + imageScore;
}
