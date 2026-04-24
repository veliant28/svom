"use client";

import { Save } from "lucide-react";
import { useEffect, useState } from "react";

export function SeoRobotsEditor({
  robotsValue,
  previewValue,
  isSaving,
  canManage,
  onSave,
  t,
}: {
  robotsValue: string;
  previewValue: string;
  isSaving: boolean;
  canManage: boolean;
  onSave: (value: string) => Promise<unknown>;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  const [value, setValue] = useState(robotsValue);

  useEffect(() => {
    setValue(robotsValue);
  }, [robotsValue]);

  const isDirty = value !== robotsValue;

  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{t("seo.sections.robots")}</p>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("seo.sections.robotsHint")}</p>
        </div>
        {canManage ? (
          <button
            type="button"
            disabled={!isDirty || isSaving}
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
            onClick={() => {
              void onSave(value);
            }}
          >
            <Save size={13} />
            {isSaving ? t("seo.actions.saving") : t("seo.actions.save")}
          </button>
        ) : null}
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <label className="grid gap-1">
          <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
            {t("seo.fields.robotsTxt")}
          </span>
          <textarea
            value={value}
            disabled={!canManage}
            onChange={(event) => setValue(event.target.value)}
            rows={10}
            className="rounded-md border px-3 py-2 text-sm font-mono"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
        </label>
        <label className="grid gap-1">
          <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
            {t("seo.fields.preview")}
          </span>
          <textarea
            value={previewValue}
            readOnly
            rows={10}
            className="rounded-md border px-3 py-2 text-sm font-mono"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
        </label>
      </div>
    </section>
  );
}
