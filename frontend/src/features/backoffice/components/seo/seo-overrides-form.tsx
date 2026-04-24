"use client";

import { Plus, Save, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import type { BackofficeSeoMetaOverride, SeoLocale } from "@/features/backoffice/api/seo-api.types";

type OverrideDraft = {
  path: string;
  locale: SeoLocale;
  meta_title: string;
  meta_description: string;
  h1: string;
  canonical_url: string;
  robots_directive: string;
  og_title: string;
  og_description: string;
  og_image_url: string;
  is_active: boolean;
};

const DEFAULT_OVERRIDE: OverrideDraft = {
  path: "/",
  locale: "uk",
  meta_title: "",
  meta_description: "",
  h1: "",
  canonical_url: "",
  robots_directive: "",
  og_title: "",
  og_description: "",
  og_image_url: "",
  is_active: true,
};

function toDraft(item: BackofficeSeoMetaOverride): OverrideDraft {
  return {
    path: item.path,
    locale: item.locale,
    meta_title: item.meta_title,
    meta_description: item.meta_description,
    h1: item.h1,
    canonical_url: item.canonical_url,
    robots_directive: item.robots_directive,
    og_title: item.og_title,
    og_description: item.og_description,
    og_image_url: item.og_image_url,
    is_active: item.is_active,
  };
}

export function SeoOverridesForm({
  overrides,
  activeActionId,
  canManage,
  onCreate,
  onUpdate,
  onDelete,
  t,
}: {
  overrides: BackofficeSeoMetaOverride[];
  activeActionId: string | null;
  canManage: boolean;
  onCreate: (payload: OverrideDraft) => Promise<BackofficeSeoMetaOverride | null>;
  onUpdate: (id: string, payload: Partial<OverrideDraft>) => Promise<BackofficeSeoMetaOverride | null>;
  onDelete: (id: string) => Promise<boolean>;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const [createDraft, setCreateDraft] = useState<OverrideDraft>(DEFAULT_OVERRIDE);
  const [drafts, setDrafts] = useState<Record<string, OverrideDraft>>({});

  const sortedOverrides = useMemo(
    () => [...overrides].sort((a, b) => `${a.path}:${a.locale}`.localeCompare(`${b.path}:${b.locale}`)),
    [overrides],
  );

  function getDraft(item: BackofficeSeoMetaOverride): OverrideDraft {
    return drafts[item.id] ?? toDraft(item);
  }

  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("seo.sections.overrides")}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("seo.sections.overridesHint")}</p>

      <article className="mt-3 rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
        <OverrideEditor draft={createDraft} disabled={!canManage} onChange={setCreateDraft} t={t} />
        {canManage ? (
          <button
            type="button"
            disabled={activeActionId !== null}
            className="mt-3 inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void onCreate(createDraft).then((created) => {
                if (created) {
                  setCreateDraft(DEFAULT_OVERRIDE);
                }
              });
            }}
          >
            <Plus size={14} />
            {t("seo.actions.create")}
          </button>
        ) : null}
      </article>

      <div className="mt-3 grid gap-3">
        {sortedOverrides.length ? sortedOverrides.map((item) => {
          const draft = getDraft(item);
          const isBusy = activeActionId === item.id;
          return (
            <article key={item.id} className="rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <OverrideEditor
                draft={draft}
                disabled={!canManage || isBusy}
                onChange={(next) => setDrafts((prev) => ({ ...prev, [item.id]: next }))}
                t={t}
              />
              {canManage ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={isBusy}
                    className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-semibold disabled:opacity-60"
                    style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
                    onClick={() => {
                      void onUpdate(item.id, draft).then((updated) => {
                        if (updated) {
                          setDrafts((prev) => {
                            const next = { ...prev };
                            delete next[item.id];
                            return next;
                          });
                        }
                      });
                    }}
                  >
                    <Save size={13} />
                    {t("seo.actions.save")}
                  </button>
                  <button
                    type="button"
                    disabled={isBusy}
                    className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-semibold disabled:opacity-60"
                    style={{ borderColor: "#dc2626", backgroundColor: "#dc2626", color: "#fff" }}
                    onClick={() => {
                      void onDelete(item.id);
                    }}
                  >
                    <Trash2 size={13} />
                    {t("seo.actions.delete")}
                  </button>
                </div>
              ) : null}
            </article>
          );
        }) : (
          <div className="rounded-lg border px-3 py-5 text-center text-sm" style={{ borderColor: "var(--border)", color: "var(--muted)" }}>
            {t("seo.states.emptyOverrides")}
          </div>
        )}
      </div>
    </section>
  );
}

function OverrideEditor({
  draft,
  disabled,
  onChange,
  t,
}: {
  draft: OverrideDraft;
  disabled: boolean;
  onChange: (next: OverrideDraft) => void;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  return (
    <div className="grid gap-2">
      <div className="grid gap-2 md:grid-cols-3">
        <InputField label={t("seo.fields.path")} value={draft.path} disabled={disabled} onChange={(next) => onChange({ ...draft, path: next })} />
        <SelectField
          label={t("seo.fields.locale")}
          value={draft.locale}
          disabled={disabled}
          onChange={(next) => onChange({ ...draft, locale: next as SeoLocale })}
        />
        <label className="inline-flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={draft.is_active} disabled={disabled} onChange={() => onChange({ ...draft, is_active: !draft.is_active })} />
          <span>{t("seo.fields.active")}</span>
        </label>
      </div>
      <InputField label={t("seo.fields.metaTitle")} value={draft.meta_title} disabled={disabled} onChange={(next) => onChange({ ...draft, meta_title: next })} />
      <TextareaField label={t("seo.fields.metaDescription")} value={draft.meta_description} disabled={disabled} onChange={(next) => onChange({ ...draft, meta_description: next })} />
      <InputField label={t("seo.fields.h1")} value={draft.h1} disabled={disabled} onChange={(next) => onChange({ ...draft, h1: next })} />
      <InputField label={t("seo.fields.canonicalUrl")} value={draft.canonical_url} disabled={disabled} onChange={(next) => onChange({ ...draft, canonical_url: next })} />
      <InputField label={t("seo.fields.robotsDirective")} value={draft.robots_directive} disabled={disabled} onChange={(next) => onChange({ ...draft, robots_directive: next })} />
      <InputField label={t("seo.fields.ogTitle")} value={draft.og_title} disabled={disabled} onChange={(next) => onChange({ ...draft, og_title: next })} />
      <TextareaField label={t("seo.fields.ogDescription")} value={draft.og_description} disabled={disabled} onChange={(next) => onChange({ ...draft, og_description: next })} />
      <InputField label={t("seo.fields.ogImageUrl")} value={draft.og_image_url} disabled={disabled} onChange={(next) => onChange({ ...draft, og_image_url: next })} />
    </div>
  );
}

function InputField({ label, value, disabled, onChange }: { label: string; value: string; disabled: boolean; onChange: (next: string) => void }) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{label}</span>
      <input
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-md border px-2 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      />
    </label>
  );
}

function TextareaField({ label, value, disabled, onChange }: { label: string; value: string; disabled: boolean; onChange: (next: string) => void }) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{label}</span>
      <textarea
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        className="rounded-md border px-2 py-2 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: SeoLocale;
  disabled: boolean;
  onChange: (next: string) => void;
}) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{label}</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-md border px-2 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <option value="uk">uk</option>
        <option value="ru">ru</option>
        <option value="en">en</option>
      </select>
    </label>
  );
}
