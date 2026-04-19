type Translator = (key: string, values?: Record<string, string | number>) => string;

export function OrderDeleteModal({
  isOpen,
  isSubmitting,
  title,
  message,
  confirmLabel,
  onConfirm,
  onClose,
  t,
}: {
  isOpen: boolean;
  isSubmitting: boolean;
  title: string;
  message: string;
  confirmLabel: string;
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
        aria-label={t("orders.actions.closeModal")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-md rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {message}
        </p>
        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border border-red-500/55 bg-red-500/12 px-3 text-xs font-semibold text-red-700 transition-colors hover:bg-red-500/20 disabled:opacity-60 dark:border-red-300/70 dark:bg-red-500/30 dark:text-red-100 dark:hover:bg-red-500/40"
            onClick={onConfirm}
          >
            {isSubmitting ? t("loading") : confirmLabel}
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onClose}
          >
            {t("orders.actions.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
