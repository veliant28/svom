import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function CategoryFormModal({
  title,
  submitLabel,
  isOpen,
  isSubmitting,
  name,
  parentId,
  isActive,
  parentOptions,
  disabledParentIds,
  getParentOptionLabel,
  onNameChange,
  onParentChange,
  onIsActiveChange,
  onClose,
  onSubmit,
  t,
}: {
  title: string;
  submitLabel: string;
  isOpen: boolean;
  isSubmitting: boolean;
  name: string;
  parentId: string;
  isActive: boolean;
  parentOptions: BackofficeCatalogCategory[];
  disabledParentIds?: Set<string>;
  getParentOptionLabel: (category: BackofficeCatalogCategory) => string;
  onNameChange: (next: string) => void;
  onParentChange: (next: string) => void;
  onIsActiveChange: (next: boolean) => void;
  onClose: () => void;
  onSubmit: () => void;
  t: Translator;
}) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("categories.actions.cancel")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-xl rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("categories.modal.subtitle")}</p>

        <div className="mt-3 grid gap-2">
          <input
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder={t("categories.fields.name")}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          <select
            value={parentId}
            onChange={(event) => onParentChange(event.target.value)}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          >
            <option value="">{t("categories.fields.parentNone")}</option>
            {parentOptions.map((item) => (
              <option key={item.id} value={item.id} disabled={Boolean(disabledParentIds?.has(item.id))}>
                {getParentOptionLabel(item)}
              </option>
            ))}
          </select>
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={isActive}
              onChange={(event) => onIsActiveChange(event.target.checked)}
            />
            {t("categories.fields.isActive")}
          </label>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onSubmit}
          >
            {submitLabel}
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onClose}
          >
            {t("categories.actions.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
