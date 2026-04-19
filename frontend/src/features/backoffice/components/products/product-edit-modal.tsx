import type { BackofficeCatalogBrand } from "@/features/backoffice/types/catalog.types";
import type { CategoryOption, ProductFormState, ProductModalMode } from "@/features/backoffice/lib/products/product-form.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ProductEditModal({
  mode,
  isOpen,
  isSubmitting,
  form,
  brands,
  categories,
  onClose,
  onSubmit,
  onChange,
  t,
}: {
  mode: ProductModalMode;
  isOpen: boolean;
  isSubmitting: boolean;
  form: ProductFormState;
  brands: BackofficeCatalogBrand[];
  categories: CategoryOption[];
  onClose: () => void;
  onSubmit: () => void;
  onChange: (next: Partial<ProductFormState>) => void;
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
      <div className="relative z-10 w-full max-w-3xl rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{mode === "create" ? t("products.create.title") : t("products.edit.title")}</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("products.modal.subtitle")}</p>

        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <input
            value={form.sku}
            onChange={(event) => onChange({ sku: event.target.value })}
            placeholder={t("products.fields.sku")}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          <input
            value={form.article}
            onChange={(event) => onChange({ article: event.target.value })}
            placeholder={t("products.fields.article")}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          <input
            value={form.name}
            onChange={(event) => onChange({ name: event.target.value })}
            placeholder={t("products.fields.name")}
            className="h-10 rounded-md border px-3 text-sm md:col-span-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          <select
            value={form.brand}
            onChange={(event) => onChange({ brand: event.target.value })}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          >
            <option value="">{t("products.fields.brand")}</option>
            {brands.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
          <select
            value={form.category}
            onChange={(event) => onChange({ category: event.target.value })}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          >
            <option value="">{t("products.fields.category")}</option>
            {categories.map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
          </select>
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => onChange({ is_active: event.target.checked })}
            />
            {t("products.flags.active")}
          </label>
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={form.is_featured}
              onChange={(event) => onChange({ is_featured: event.target.checked })}
            />
            {t("products.flags.featured")}
          </label>
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={form.is_new}
              onChange={(event) => onChange({ is_new: event.target.checked })}
            />
            {t("products.flags.new")}
          </label>
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={form.is_bestseller}
              onChange={(event) => onChange({ is_bestseller: event.target.checked })}
            />
            {t("products.flags.bestseller")}
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
            {mode === "create" ? t("products.actions.create") : t("products.actions.save")}
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
