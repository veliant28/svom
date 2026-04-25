import { useTranslations } from "next-intl";

import { PercentStepper } from "@/features/backoffice/components/pricing/percent-stepper";
import { clampNumber, type SlideForm } from "@/features/backoffice/lib/hero-block-page.helpers";

export function LocaleFields({
  titleLabel,
  subtitleLabel,
  form,
  onChange,
}: {
  titleLabel: string;
  subtitleLabel: string;
  form: SlideForm;
  onChange: (updater: (prev: SlideForm) => SlideForm) => void;
}) {
  const t = useTranslations("backoffice.common");

  function updateField(key: keyof SlideForm, value: string) {
    onChange((prev: SlideForm) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <div className="min-w-0 grid gap-3">
        <TextField label={`${titleLabel} (uk)`} value={form.title_uk} onChange={(next) => updateField("title_uk", next)} />
        <TextAreaField label={`${subtitleLabel} (uk)`} value={form.subtitle_uk} onChange={(next) => updateField("subtitle_uk", next)} />
      </div>
      <div className="min-w-0 grid gap-3">
        <TextField label={`${titleLabel} (ru)`} value={form.title_ru} onChange={(next) => updateField("title_ru", next)} />
        <TextAreaField label={`${subtitleLabel} (ru)`} value={form.subtitle_ru} onChange={(next) => updateField("subtitle_ru", next)} />
      </div>
      <div className="min-w-0 grid gap-3">
        <TextField label={`${titleLabel} (en)`} value={form.title_en} onChange={(next) => updateField("title_en", next)} />
        <TextAreaField label={`${subtitleLabel} (en)`} value={form.subtitle_en} onChange={(next) => updateField("subtitle_en", next)} />
      </div>
      <p className="lg:col-span-3 text-xs" style={{ color: "var(--muted)" }}>
        {t("heroBlock.fields.localizationHint")}
      </p>
    </div>
  );
}

export function TextField({
  label,
  labelClassName,
  wrapperClassName,
  value,
  onChange,
}: {
  label: string;
  labelClassName?: string;
  wrapperClassName?: string;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className={`min-w-0 grid gap-1 ${wrapperClassName ?? ""}`.trim()}>
      <span className={`text-xs font-semibold uppercase leading-tight tracking-[0.08em] ${labelClassName ?? ""}`.trim()} style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <input
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="h-9 rounded-md border px-2 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      />
    </label>
  );
}

function TextAreaField({ label, value, onChange }: { label: string; value: string; onChange: (next: string) => void }) {
  return (
    <label className="min-w-0 grid gap-1">
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <textarea
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        rows={4}
        className="rounded-md border px-2 py-2 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      />
    </label>
  );
}

export function FileField({
  label,
  labelClassName,
  wrapperClassName,
  onChange,
  currentImageUrl,
  selectedFile,
}: {
  label: string;
  labelClassName?: string;
  wrapperClassName?: string;
  onChange: (file: File | null) => void;
  currentImageUrl?: string;
  selectedFile?: File | null;
}) {
  const t = useTranslations("backoffice.common");
  const currentFileName = getFileNameFromUrl(currentImageUrl || "");
  const selectedFileName = (selectedFile?.name || "").trim();

  return (
    <label className={`min-w-0 grid gap-1 ${wrapperClassName ?? ""}`.trim()}>
      <span className={`text-xs font-semibold uppercase leading-tight tracking-[0.08em] ${labelClassName ?? ""}`.trim()} style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <input
        type="file"
        accept="image/*"
        className="h-9 w-full min-w-0 overflow-hidden rounded-md border px-2 text-xs leading-9 file:mr-2 file:h-7 file:max-w-full file:rounded file:border-0 file:px-2 file:text-xs file:leading-7"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", lineHeight: "2.25rem" }}
        onChange={(event) => {
          onChange(event.target.files?.[0] || null);
        }}
      />
      {currentFileName ? (
        <span className="text-xs" style={{ color: "var(--muted)" }}>
          {t("heroBlock.fields.currentImageSaved", { name: currentFileName })}
        </span>
      ) : null}
      <span className="text-xs" style={{ color: "var(--muted)" }}>
        {selectedFileName
          ? t("heroBlock.fields.newFileSelected", { name: selectedFileName })
          : currentFileName
            ? t("heroBlock.fields.replaceImageHint")
            : t("heroBlock.fields.noFileSelected")}
      </span>
    </label>
  );
}

function getFileNameFromUrl(value: string): string {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "";
  }
  const pathname = normalized.split("?")[0].split("#")[0];
  return pathname.split("/").filter(Boolean).pop() || "";
}

export function ToggleField({
  label,
  widthClassName,
  value,
  onToggle,
  yesLabel,
  noLabel,
}: {
  label: string;
  widthClassName?: string;
  value: boolean;
  onToggle: () => void;
  yesLabel: string;
  noLabel: string;
}) {
  const wrapperClassName = widthClassName ? `grid gap-1 ${widthClassName}` : "grid min-w-[140px] gap-1";

  return (
    <label className={wrapperClassName}>
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <button
        type="button"
        className="h-9 rounded-md border px-3 text-sm font-semibold"
        style={{
          borderColor: value ? "var(--text)" : "var(--border)",
          backgroundColor: value ? "var(--text)" : "var(--surface)",
          color: value ? "var(--surface)" : "var(--text)",
        }}
        onClick={onToggle}
      >
        {value ? yesLabel : noLabel}
      </button>
    </label>
  );
}

export function ImagePreview({ imageUrl, label }: { imageUrl: string; label: string }) {
  return (
    <div className="grid gap-1">
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <div className="min-h-[140px] rounded-lg border bg-cover bg-center" style={{ borderColor: "var(--border)", backgroundImage: `url(${imageUrl})` }} />
    </div>
  );
}

export function NumberStepper({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (next: number) => void;
  min: number;
  max: number;
  step?: number;
}) {
  const safeValue = clampNumber(value, min, max);
  return (
    <label className="grid min-w-[140px] gap-1 justify-items-start">
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <PercentStepper
        value={safeValue}
        onChange={onChange}
        min={min}
        max={max}
        step={step}
        minusLabel={`${label} -`}
        plusLabel={`${label} +`}
        inputLabel={label}
        suffix=""
        inputMode="numeric"
        integerOnly
        inputWidthClassName="w-12"
        containerClassName="w-[118px]"
      />
    </label>
  );
}
