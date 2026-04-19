type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ProductDeleteModal({
  isOpen,
  isSubmitting,
  productName,
  onConfirm,
  onClose,
  t,
}: {
  isOpen: boolean;
  isSubmitting: boolean;
  productName: string;
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
      <div className="relative z-10 w-full max-w-md rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{t("products.actions.delete")}</h2>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("products.messages.deleteConfirm", { name: productName })}
        </p>
        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onConfirm}
          >
            {isSubmitting ? t("loading") : t("products.actions.delete")}
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
