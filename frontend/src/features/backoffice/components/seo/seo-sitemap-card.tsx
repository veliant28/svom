"use client";

import { RefreshCw, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { BackofficeSeoSettings, BackofficeSeoSitemapRebuildResponse } from "@/features/backoffice/api/seo-api.types";

type SitemapForm = Pick<
BackofficeSeoSettings,
  "sitemap_enabled" | "product_sitemap_enabled" | "category_sitemap_enabled" | "brand_sitemap_enabled"
>;

function toForm(settings: BackofficeSeoSettings | null): SitemapForm {
  return {
    sitemap_enabled: settings?.sitemap_enabled ?? true,
    product_sitemap_enabled: settings?.product_sitemap_enabled ?? true,
    category_sitemap_enabled: settings?.category_sitemap_enabled ?? true,
    brand_sitemap_enabled: settings?.brand_sitemap_enabled ?? true,
  };
}

export function SeoSitemapCard({
  settings,
  lastSitemapResult,
  isSavingSettings,
  isRebuilding,
  canManage,
  onSaveSettings,
  onRebuild,
  t,
}: {
  settings: BackofficeSeoSettings | null;
  lastSitemapResult: BackofficeSeoSitemapRebuildResponse | null;
  isSavingSettings: boolean;
  isRebuilding: boolean;
  canManage: boolean;
  onSaveSettings: (payload: Partial<BackofficeSeoSettings>) => Promise<BackofficeSeoSettings | null>;
  onRebuild: () => Promise<BackofficeSeoSitemapRebuildResponse | null>;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const [form, setForm] = useState<SitemapForm>(() => toForm(settings));

  useEffect(() => {
    setForm(toForm(settings));
  }, [settings]);

  const isDirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(toForm(settings)), [form, settings]);

  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("seo.sections.sitemap")}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("seo.sections.sitemapHint")}</p>

      <div className="mt-3 grid gap-2">
        <ToggleField label={t("seo.fields.sitemapEnabled")} checked={form.sitemap_enabled} disabled={!canManage} onToggle={() => setForm((prev) => ({ ...prev, sitemap_enabled: !prev.sitemap_enabled }))} />
        <ToggleField label={t("seo.fields.productSitemapEnabled")} checked={form.product_sitemap_enabled} disabled={!canManage} onToggle={() => setForm((prev) => ({ ...prev, product_sitemap_enabled: !prev.product_sitemap_enabled }))} />
        <ToggleField label={t("seo.fields.categorySitemapEnabled")} checked={form.category_sitemap_enabled} disabled={!canManage} onToggle={() => setForm((prev) => ({ ...prev, category_sitemap_enabled: !prev.category_sitemap_enabled }))} />
        <ToggleField label={t("seo.fields.brandSitemapEnabled")} checked={form.brand_sitemap_enabled} disabled={!canManage} onToggle={() => setForm((prev) => ({ ...prev, brand_sitemap_enabled: !prev.brand_sitemap_enabled }))} />
      </div>

      {lastSitemapResult?.rebuilt_at ? (
        <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>
          {t("seo.sitemap.lastRebuilt", { datetime: lastSitemapResult.rebuilt_at })}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        {canManage ? (
          <button
            type="button"
            disabled={!isDirty || isSavingSettings}
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
            onClick={() => {
              void onSaveSettings(form);
            }}
          >
            <Save size={13} />
            {isSavingSettings ? t("seo.actions.saving") : t("seo.actions.save")}
          </button>
        ) : null}

        {canManage ? (
          <button
            type="button"
            disabled={isRebuilding}
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={() => {
              void onRebuild();
            }}
          >
            <RefreshCw size={13} className={isRebuilding ? "animate-spin" : ""} />
            {t("seo.actions.rebuildSitemap")}
          </button>
        ) : null}
      </div>
    </section>
  );
}

function ToggleField({
  label,
  checked,
  disabled,
  onToggle,
}: {
  label: string;
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="inline-flex items-center gap-2 text-sm font-medium">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle} />
      <span>{label}</span>
    </label>
  );
}
