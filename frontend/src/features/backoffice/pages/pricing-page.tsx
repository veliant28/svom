"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Layers, RefreshCw } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import {
  getBackofficeCatalogCategories,
  getBackofficePricingCategoryImpact,
  getBackofficePricingControlPanel,
  runBackofficePricingRecalculate,
  updateBackofficePricingCategoryMarkup,
  updateBackofficePricingGlobalMarkup,
} from "@/features/backoffice/api/backoffice-api";
import { HelpLabel } from "@/features/backoffice/components/pricing/help-label";
import { PercentStepper } from "@/features/backoffice/components/pricing/percent-stepper";
import { PricingMarkupChart } from "@/features/backoffice/components/pricing/pricing-markup-chart";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeCatalogCategory } from "@/features/backoffice/types/backoffice";

type CategoryOption = {
  id: string;
  label: string;
};

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}

function toPercent(value: string | null | undefined): number {
  const parsed = Number(value ?? 0);
  return clampPercent(parsed);
}

function getLocalizedCategoryName(category: BackofficeCatalogCategory, locale: string): string {
  if (locale === "ru") {
    return category.name_ru || category.name_uk || category.name;
  }
  if (locale === "en") {
    return category.name_en || category.name_uk || category.name;
  }
  return category.name_uk || category.name;
}

export function PricingPage() {
  const locale = useLocale();
  const t = useTranslations("backoffice.common");
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const controlPanelQuery = useCallback((token: string) => getBackofficePricingControlPanel(token), []);
  const categoriesQuery = useCallback(
    async (token: string) => {
      const results: BackofficeCatalogCategory[] = [];
      let page = 1;
      while (true) {
        const chunk = await getBackofficeCatalogCategories(token, { page, page_size: 500, locale });
        results.push(...chunk.results);
        if (results.length >= chunk.count || chunk.results.length === 0) {
          break;
        }
        page += 1;
      }
      return { count: results.length, results };
    },
    [locale],
  );

  const controlPanel = useBackofficeQuery(controlPanelQuery, []);
  const categoriesData = useBackofficeQuery<{ count: number; results: BackofficeCatalogCategory[] }>(categoriesQuery, [locale]);

  const [search, setSearch] = useState("");
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [includeChildren, setIncludeChildren] = useState(true);
  const [globalPercent, setGlobalPercent] = useState(0);
  const [categoryPercent, setCategoryPercent] = useState(0);
  const [isApplyingGlobal, setIsApplyingGlobal] = useState(false);
  const [isApplyingCategory, setIsApplyingCategory] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);

  const impactQueryFn = useCallback(
    (token: string) => {
      if (!selectedCategoryId) {
        return Promise.resolve(null);
      }
      return getBackofficePricingCategoryImpact(token, { category_id: selectedCategoryId, include_children: includeChildren });
    },
    [includeChildren, selectedCategoryId],
  );
  const impactData = useBackofficeQuery(impactQueryFn, [selectedCategoryId, includeChildren]);
  const globalPercentValue = toPercent(controlPanel.data?.global_policy?.percent_markup);
  const selectedImpact = useMemo(() => {
    if (!selectedCategoryId || !impactData.data) {
      return null;
    }
    return impactData.data.category_id === selectedCategoryId ? impactData.data : null;
  }, [impactData.data, selectedCategoryId]);

  useEffect(() => {
    setGlobalPercent(globalPercentValue);
  }, [globalPercentValue]);

  useEffect(() => {
    if (!selectedCategoryId) {
      setCategoryPercent(globalPercentValue);
      return;
    }

    const next = toPercent(selectedImpact?.current_percent_markup ?? controlPanel.data?.global_policy?.percent_markup);
    setCategoryPercent(next);
  }, [controlPanel.data?.global_policy?.percent_markup, globalPercentValue, selectedCategoryId, selectedImpact?.current_percent_markup]);

  const categoryOptions = useMemo<CategoryOption[]>(() => {
    const rows = categoriesData.data?.results ?? [];
    const byId = rows.reduce<Record<string, BackofficeCatalogCategory>>((acc, category) => {
      acc[category.id] = category;
      return acc;
    }, {});

    const buildPath = (row: BackofficeCatalogCategory): string => {
      const chain: string[] = [];
      let current: BackofficeCatalogCategory | undefined = row;
      const visited = new Set<string>();
      while (current && !visited.has(current.id)) {
        visited.add(current.id);
        chain.unshift(getLocalizedCategoryName(current, locale));
        current = current.parent ? byId[current.parent] : undefined;
      }
      return chain.join(" > ");
    };

    return rows
      .map((row) => ({ id: row.id, label: buildPath(row) }))
      .sort((left, right) => left.label.localeCompare(right.label, locale));
  }, [categoriesData.data?.results, locale]);

  const filteredOptions = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    if (!normalized) {
      return categoryOptions;
    }
    return categoryOptions.filter((option) => option.label.toLowerCase().includes(normalized));
  }, [categoryOptions, search]);

  const applyGlobalMarkup = useCallback(async () => {
    if (!controlPanel.token || isApplyingGlobal) {
      return;
    }
    setIsApplyingGlobal(true);
    try {
      const response = await updateBackofficePricingGlobalMarkup(controlPanel.token, {
        percent_markup: clampPercent(globalPercent),
        dispatch_async: true,
      });
      showSuccess(
        t("pricing.messages.globalApplied", {
          count: response.affected_products,
          mode: response.mode,
        }),
      );
      await controlPanel.refetch();
    } catch (error) {
      showApiError(error, t("pricing.messages.globalFailed"));
    } finally {
      setIsApplyingGlobal(false);
    }
  }, [controlPanel, globalPercent, isApplyingGlobal, showApiError, showSuccess, t]);

  const applyCategoryMarkup = useCallback(async () => {
    if (!controlPanel.token || !selectedCategoryId || isApplyingCategory) {
      return;
    }
    setIsApplyingCategory(true);
    try {
      const response = await updateBackofficePricingCategoryMarkup(controlPanel.token, {
        category_id: selectedCategoryId,
        percent_markup: clampPercent(categoryPercent),
        include_children: includeChildren,
        dispatch_async: true,
      });
      showSuccess(
        t("pricing.messages.categoryApplied", {
          count: response.affected_products,
          categories: response.target_categories,
        }),
      );
      await Promise.all([controlPanel.refetch(), impactData.refetch()]);
    } catch (error) {
      showApiError(error, t("pricing.messages.categoryFailed"));
    } finally {
      setIsApplyingCategory(false);
    }
  }, [categoryPercent, controlPanel, impactData, includeChildren, isApplyingCategory, selectedCategoryId, showApiError, showSuccess, t]);

  const runRecalculate = useCallback(
    async (scope: "all" | "category") => {
      if (!controlPanel.token || isRecalculating) {
        return;
      }
      if (scope === "category" && !selectedCategoryId) {
        return;
      }
      setIsRecalculating(true);
      try {
        const response = await runBackofficePricingRecalculate(controlPanel.token, {
          dispatch_async: true,
          category_id: scope === "category" ? selectedCategoryId : undefined,
          include_children: scope === "category" ? includeChildren : undefined,
        });
        showSuccess(t("pricing.messages.recalculateQueued", { count: response.affected_products, mode: response.mode }));
        await controlPanel.refetch();
      } catch (error) {
        showApiError(error, t("pricing.messages.recalculateFailed"));
      } finally {
        setIsRecalculating(false);
      }
    },
    [controlPanel, includeChildren, isRecalculating, selectedCategoryId, showApiError, showSuccess, t],
  );

  return (
    <section>
      <PageHeader
        title={t("pricing.title")}
        description={t("pricing.subtitle")}
        actions={
          <button
            type="button"
            className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void Promise.all([controlPanel.refetch(), categoriesData.refetch(), impactData.refetch()]);
            }}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
            {t("pricing.actions.refresh")}
          </button>
        }
      />

      <AsyncState isLoading={controlPanel.isLoading || categoriesData.isLoading} error={controlPanel.error || categoriesData.error} empty={!controlPanel.data} emptyLabel={t("pricing.states.empty")}>
        {controlPanel.data ? (
          <div className="grid gap-4">
            <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <div className="mb-2 flex items-center justify-between gap-2">
                <HelpLabel label={t("pricing.blocks.chart.title")} tooltip={t("pricing.tooltips.chart")} />
                <span className="text-xs" style={{ color: "var(--muted)" }}>{t("pricing.blocks.chart.subtitle")}</span>
              </div>
              <PricingMarkupChart items={controlPanel.data.chart.markup_buckets} emptyLabel={t("pricing.states.chartEmpty")} />
            </section>

            <div className="grid gap-4 xl:grid-cols-2">
              <section className="min-w-0 rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <HelpLabel label={t("pricing.blocks.global.title")} tooltip={t("pricing.tooltips.global")} />
                <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                  {t("pricing.blocks.global.scope", { count: controlPanel.data.summary.products_total })}
                </p>
                <div className="mt-3">
                  <PercentStepper
                    value={globalPercent}
                    onChange={setGlobalPercent}
                    minusLabel={t("pricing.actions.decrease")}
                    plusLabel={t("pricing.actions.increase")}
                    inputLabel={t("pricing.fields.globalPercent")}
                  />
                </div>
                <button
                  type="button"
                  disabled={isApplyingGlobal}
                  className="mt-3 h-9 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  onClick={() => {
                    void applyGlobalMarkup();
                  }}
                >
                  {t("pricing.actions.applyGlobal")}
                </button>
              </section>

              <section className="min-w-0 rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <HelpLabel label={t("pricing.blocks.category.title")} tooltip={t("pricing.tooltips.category")} />
                <div className="mt-2 grid gap-2">
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder={t("pricing.fields.categorySearch")}
                    className="h-9 w-full min-w-0 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  />
                  <select
                    value={selectedCategoryId}
                    onChange={(event) => setSelectedCategoryId(event.target.value)}
                    className="h-9 w-full min-w-0 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  >
                    <option value="">{t("pricing.fields.selectCategory")}</option>
                    {filteredOptions.map((option) => (
                      <option key={option.id} value={option.id}>{option.label}</option>
                    ))}
                  </select>
                  <label className="inline-flex items-center gap-2 text-xs" style={{ color: "var(--muted)" }}>
                    <input
                      type="checkbox"
                      checked={includeChildren}
                      onChange={(event) => setIncludeChildren(event.target.checked)}
                    />
                    {t("pricing.fields.includeChildren")}
                  </label>
                </div>

                <div className="mt-3">
                  <PercentStepper
                    value={categoryPercent}
                    onChange={setCategoryPercent}
                    minusLabel={t("pricing.actions.decrease")}
                    plusLabel={t("pricing.actions.increase")}
                    inputLabel={t("pricing.fields.categoryPercent")}
                  />
                </div>

                <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                  {t("pricing.blocks.category.impact", { count: selectedImpact?.affected_products ?? 0 })}
                </p>
                <button
                  type="button"
                  disabled={!selectedCategoryId || isApplyingCategory}
                  className="mt-2 h-9 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  onClick={() => {
                    void applyCategoryMarkup();
                  }}
                >
                  {t("pricing.actions.applyCategory")}
                </button>
              </section>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <HelpLabel label={t("pricing.blocks.top.title")} tooltip={t("pricing.tooltips.top")} />
                <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                  {controlPanel.data.top_segment.supported ? t("pricing.blocks.top.ready") : t("pricing.blocks.top.unavailable")}
                </p>
                <div className="mt-2 inline-flex items-center gap-2 rounded-md border px-2 py-1 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}>
                  <Layers className="h-3.5 w-3.5" />
                  {t("pricing.blocks.top.stats", { top: controlPanel.data.summary.featured_total, other: controlPanel.data.summary.non_featured_total })}
                </div>
              </section>

              <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <HelpLabel label={t("pricing.blocks.recalculate.title")} tooltip={t("pricing.tooltips.recalculate")} />
                <div className="mt-3 flex flex-wrap gap-2">
                  <BackofficeTooltip content={t("pricing.tooltips.recalculateAll")} placement="top">
                    <button
                      type="button"
                      disabled={isRecalculating}
                      className="h-9 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        void runRecalculate("all");
                      }}
                    >
                      {t("pricing.actions.recalculateAll")}
                    </button>
                  </BackofficeTooltip>
                  <BackofficeTooltip content={t("pricing.tooltips.recalculateCategory")} placement="top">
                    <button
                      type="button"
                      disabled={isRecalculating || !selectedCategoryId}
                      className="h-9 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        void runRecalculate("category");
                      }}
                    >
                      {t("pricing.actions.recalculateCategory")}
                    </button>
                  </BackofficeTooltip>
                </div>
              </section>
            </div>
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
