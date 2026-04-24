"use client";

import { Save, Trash2, Plus } from "lucide-react";
import { useMemo, useState } from "react";

import type { BackofficeSeoMetaTemplate, SeoEntityType, SeoLocale } from "@/features/backoffice/api/seo-api.types";

type TemplateDraft = {
  entity_type: SeoEntityType;
  locale: SeoLocale;
  title_template: string;
  description_template: string;
  h1_template: string;
  og_title_template: string;
  og_description_template: string;
  is_active: boolean;
};

const DEFAULT_DRAFT: TemplateDraft = {
  entity_type: "product",
  locale: "uk",
  title_template: "",
  description_template: "",
  h1_template: "",
  og_title_template: "",
  og_description_template: "",
  is_active: true,
};

function toDraft(item: BackofficeSeoMetaTemplate): TemplateDraft {
  return {
    entity_type: item.entity_type,
    locale: item.locale,
    title_template: item.title_template,
    description_template: item.description_template,
    h1_template: item.h1_template,
    og_title_template: item.og_title_template,
    og_description_template: item.og_description_template,
    is_active: item.is_active,
  };
}

export function SeoMetaTemplatesForm({
  templates,
  activeActionId,
  canManage,
  onCreate,
  onUpdate,
  onDelete,
  t,
}: {
  templates: BackofficeSeoMetaTemplate[];
  activeActionId: string | null;
  canManage: boolean;
  onCreate: (payload: TemplateDraft) => Promise<BackofficeSeoMetaTemplate | null>;
  onUpdate: (id: string, payload: Partial<TemplateDraft>) => Promise<BackofficeSeoMetaTemplate | null>;
  onDelete: (id: string) => Promise<boolean>;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const [createDraft, setCreateDraft] = useState<TemplateDraft>(DEFAULT_DRAFT);
  const [drafts, setDrafts] = useState<Record<string, TemplateDraft>>({});

  const sortedTemplates = useMemo(
    () => [...templates].sort((a, b) => `${a.entity_type}:${a.locale}`.localeCompare(`${b.entity_type}:${b.locale}`)),
    [templates],
  );

  function getDraft(item: BackofficeSeoMetaTemplate): TemplateDraft {
    return drafts[item.id] ?? toDraft(item);
  }

  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("seo.sections.templates")}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("seo.sections.templatesHint")}</p>

      <article className="mt-3 rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
        <p className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
          {t("seo.actions.create")}
        </p>
        <TemplateEditor
          draft={createDraft}
          disabled={!canManage}
          t={t}
          onChange={setCreateDraft}
        />
        {canManage ? (
          <button
            type="button"
            disabled={activeActionId !== null}
            className="mt-3 inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void onCreate(createDraft).then((created) => {
                if (created) {
                  setCreateDraft(DEFAULT_DRAFT);
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
        {sortedTemplates.length ? sortedTemplates.map((item) => {
          const draft = getDraft(item);
          const isBusy = activeActionId === item.id;
          return (
            <article key={item.id} className="rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <TemplateEditor
                draft={draft}
                disabled={!canManage || isBusy}
                t={t}
                onChange={(next) => setDrafts((prev) => ({ ...prev, [item.id]: next }))}
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
            {t("seo.states.emptyTemplates")}
          </div>
        )}
      </div>
    </section>
  );
}

function TemplateEditor({
  draft,
  disabled,
  onChange,
  t,
}: {
  draft: TemplateDraft;
  disabled: boolean;
  onChange: (next: TemplateDraft) => void;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  return (
    <div className="grid gap-2">
      <div className="grid gap-2 md:grid-cols-3">
        <SelectField
          label={t("seo.fields.entityType")}
          value={draft.entity_type}
          disabled={disabled}
          onChange={(next) => onChange({ ...draft, entity_type: next as SeoEntityType })}
          options={[
            { value: "product", label: t("seo.entities.product") },
            { value: "category", label: t("seo.entities.category") },
            { value: "brand", label: t("seo.entities.brand") },
            { value: "page", label: t("seo.entities.page") },
          ]}
        />
        <SelectField
          label={t("seo.fields.locale")}
          value={draft.locale}
          disabled={disabled}
          onChange={(next) => onChange({ ...draft, locale: next as SeoLocale })}
          options={[
            { value: "uk", label: "uk" },
            { value: "ru", label: "ru" },
            { value: "en", label: "en" },
          ]}
        />
        <label className="inline-flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            checked={draft.is_active}
            disabled={disabled}
            onChange={() => onChange({ ...draft, is_active: !draft.is_active })}
          />
          <span>{t("seo.fields.active")}</span>
        </label>
      </div>

      <InputField label={t("seo.fields.titleTemplate")} value={draft.title_template} disabled={disabled} onChange={(next) => onChange({ ...draft, title_template: next })} />
      <InputField label={t("seo.fields.h1Template")} value={draft.h1_template} disabled={disabled} onChange={(next) => onChange({ ...draft, h1_template: next })} />
      <InputField label={t("seo.fields.ogTitleTemplate")} value={draft.og_title_template} disabled={disabled} onChange={(next) => onChange({ ...draft, og_title_template: next })} />
      <TextareaField
        label={t("seo.fields.descriptionTemplate")}
        value={draft.description_template}
        disabled={disabled}
        onChange={(next) => onChange({ ...draft, description_template: next })}
      />
      <TextareaField
        label={t("seo.fields.ogDescriptionTemplate")}
        value={draft.og_description_template}
        disabled={disabled}
        onChange={(next) => onChange({ ...draft, og_description_template: next })}
      />
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
  options,
}: {
  label: string;
  value: string;
  disabled: boolean;
  onChange: (next: string) => void;
  options: Array<{ value: string; label: string }>;
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
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}
