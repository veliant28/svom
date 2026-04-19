import type { CategoryOption } from "@/features/backoffice/lib/products/product-form.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ProductBulkCategoryModal({
  isOpen,
  isSubmitting,
  count,
  categories,
  selectedCategoryId,
  onCategoryChange,
  onConfirm,
  onClose,
  t,
}: {
  isOpen: boolean;
  isSubmitting: boolean;
  count: number;
  categories: CategoryOption[];
  selectedCategoryId: string;
  onCategoryChange: (value: string) => void;
  onConfirm: () => void;
  onClose: () => void;
  t: Translator;
}) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("products.actions.cancel")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div
        className="relative z-10 w-full max-w-md rounded-xl border p-4"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <h2 className="text-sm font-semibold">{t("products.actions.bulkMoveCategory")}</h2>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("products.messages.bulkMoveCategoryConfirm", { count })}
        </p>

        <label className="mt-3 flex flex-col gap-1 text-xs">
          {t("products.fields.category")}
          <select
            value={selectedCategoryId}
            onChange={(event) => onCategoryChange(event.target.value)}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          >
            <option value="">{t("products.messages.bulkMoveCategorySelect")}</option>
            {categories.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            disabled={isSubmitting || !selectedCategoryId}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onConfirm}
          >
            {isSubmitting ? t("loading") : t("products.actions.save")}
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onClose}
          >
            {t("products.actions.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
