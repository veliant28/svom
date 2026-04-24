"use client";

import { Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { BackofficeSeoSettings } from "@/features/backoffice/api/seo-api.types";

type SeoSettingsFormState = Pick<
BackofficeSeoSettings,
  | "is_enabled"
  | "default_meta_title_uk"
  | "default_meta_title_ru"
  | "default_meta_title_en"
  | "default_meta_description_uk"
  | "default_meta_description_ru"
  | "default_meta_description_en"
  | "default_og_title_uk"
  | "default_og_title_ru"
  | "default_og_title_en"
  | "default_og_description_uk"
  | "default_og_description_ru"
  | "default_og_description_en"
  | "default_robots_directive"
  | "canonical_base_url"
>;

function toForm(settings: BackofficeSeoSettings | null): SeoSettingsFormState {
  return {
    is_enabled: settings?.is_enabled ?? true,
    default_meta_title_uk: settings?.default_meta_title_uk ?? "",
    default_meta_title_ru: settings?.default_meta_title_ru ?? "",
    default_meta_title_en: settings?.default_meta_title_en ?? "",
    default_meta_description_uk: settings?.default_meta_description_uk ?? "",
    default_meta_description_ru: settings?.default_meta_description_ru ?? "",
    default_meta_description_en: settings?.default_meta_description_en ?? "",
    default_og_title_uk: settings?.default_og_title_uk ?? "",
    default_og_title_ru: settings?.default_og_title_ru ?? "",
    default_og_title_en: settings?.default_og_title_en ?? "",
    default_og_description_uk: settings?.default_og_description_uk ?? "",
    default_og_description_ru: settings?.default_og_description_ru ?? "",
    default_og_description_en: settings?.default_og_description_en ?? "",
    default_robots_directive: settings?.default_robots_directive ?? "index,follow",
    canonical_base_url: settings?.canonical_base_url ?? "",
  };
}

export function SeoSettingsForm({
  settings,
  isSaving,
  canManage,
  onSave,
  t,
}: {
  settings: BackofficeSeoSettings | null;
  isSaving: boolean;
  canManage: boolean;
  onSave: (payload: Partial<BackofficeSeoSettings>) => Promise<BackofficeSeoSettings | null>;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const [form, setForm] = useState<SeoSettingsFormState>(() => toForm(settings));

  useEffect(() => {
    setForm(toForm(settings));
  }, [settings]);

  const isDirty = useMemo(() => {
    const baseline = toForm(settings);
    return JSON.stringify(baseline) !== JSON.stringify(form);
  }, [form, settings]);

  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{t("seo.sections.globalSettings")}</p>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("seo.sections.globalSettingsHint")}</p>
        </div>
        {canManage ? (
          <button
            type="button"
            disabled={!isDirty || isSaving}
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
            onClick={() => {
              void onSave(form);
            }}
          >
            <Save size={13} />
            {isSaving ? t("seo.actions.saving") : t("seo.actions.save")}
          </button>
        ) : null}
      </div>

      <div className="grid gap-3">
        <ToggleField
          label={t("seo.fields.enabled")}
          checked={form.is_enabled}
          disabled={!canManage}
          onToggle={() => {
            setForm((prev) => ({ ...prev, is_enabled: !prev.is_enabled }));
          }}
        />
        <label className="grid gap-1">
          <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
            {t("seo.fields.canonicalBaseUrl")}
          </span>
          <input
            value={form.canonical_base_url}
            disabled={!canManage}
            onChange={(event) => setForm((prev) => ({ ...prev, canonical_base_url: event.target.value }))}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            placeholder={t("seo.placeholders.canonicalBaseUrl")}
          />
        </label>
        <label className="grid gap-1">
          <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
            {t("seo.fields.defaultRobotsDirective")}
          </span>
          <input
            value={form.default_robots_directive}
            disabled={!canManage}
            onChange={(event) => setForm((prev) => ({ ...prev, default_robots_directive: event.target.value }))}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            placeholder={t("seo.placeholders.robotsDirective")}
          />
        </label>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <LocalizedFields
          title={t("seo.fields.defaultMetaTitle")}
          description={t("seo.fields.defaultMetaDescription")}
          values={{
            title_uk: form.default_meta_title_uk,
            title_ru: form.default_meta_title_ru,
            title_en: form.default_meta_title_en,
            description_uk: form.default_meta_description_uk,
            description_ru: form.default_meta_description_ru,
            description_en: form.default_meta_description_en,
          }}
          disabled={!canManage}
          onChange={(patch) => {
            setForm((prev) => ({ ...prev, ...patch }));
          }}
        />
        <LocalizedFields
          title={t("seo.fields.defaultOgTitle")}
          description={t("seo.fields.defaultOgDescription")}
          values={{
            title_uk: form.default_og_title_uk,
            title_ru: form.default_og_title_ru,
            title_en: form.default_og_title_en,
            description_uk: form.default_og_description_uk,
            description_ru: form.default_og_description_ru,
            description_en: form.default_og_description_en,
          }}
          disabled={!canManage}
          onChange={(patch) => {
            setForm((prev) => ({ ...prev, ...patch }));
          }}
        />
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

function LocalizedFields({
  title,
  description,
  values,
  disabled,
  onChange,
}: {
  title: string;
  description: string;
  values: {
    title_uk: string;
    title_ru: string;
    title_en: string;
    description_uk: string;
    description_ru: string;
    description_en: string;
  };
  disabled: boolean;
  onChange: (patch: Record<string, string>) => void;
}) {
  return (
    <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <p className="text-sm font-semibold">{title}</p>
      <div className="mt-2 grid gap-2 lg:grid-cols-3">
        <LocaleColumn
          locale="uk"
          titleLabel={title}
          titleValue={values.title_uk}
          descriptionValue={values.description_uk}
          descriptionLabel={description}
          disabled={disabled}
          onTitleChange={(next) => onChange({ title_uk: next })}
          onDescriptionChange={(next) => onChange({ description_uk: next })}
        />
        <LocaleColumn
          locale="ru"
          titleLabel={title}
          titleValue={values.title_ru}
          descriptionValue={values.description_ru}
          descriptionLabel={description}
          disabled={disabled}
          onTitleChange={(next) => onChange({ title_ru: next })}
          onDescriptionChange={(next) => onChange({ description_ru: next })}
        />
        <LocaleColumn
          locale="en"
          titleLabel={title}
          titleValue={values.title_en}
          descriptionValue={values.description_en}
          descriptionLabel={description}
          disabled={disabled}
          onTitleChange={(next) => onChange({ title_en: next })}
          onDescriptionChange={(next) => onChange({ description_en: next })}
        />
      </div>
    </div>
  );
}

function LocaleColumn({
  locale,
  titleLabel,
  titleValue,
  descriptionValue,
  descriptionLabel,
  disabled,
  onTitleChange,
  onDescriptionChange,
}: {
  locale: "uk" | "ru" | "en";
  titleLabel: string;
  titleValue: string;
  descriptionValue: string;
  descriptionLabel: string;
  disabled: boolean;
  onTitleChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-1">
      <label className="grid gap-1">
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
          {titleLabel} ({locale})
        </span>
        <input
          value={titleValue}
          disabled={disabled}
          onChange={(event) => onTitleChange(event.target.value)}
          className="h-9 rounded-md border px-2 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
      </label>
      <label className="grid gap-1">
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
          {descriptionLabel} ({locale})
        </span>
        <textarea
          value={descriptionValue}
          disabled={disabled}
          onChange={(event) => onDescriptionChange(event.target.value)}
          rows={3}
          className="rounded-md border px-2 py-2 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
      </label>
    </div>
  );
}
