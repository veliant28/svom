
type Translator = (key: string, values?: Record<string, string | number>) => string;

export function CategoryRowActions({
  t,
  isDeleting,
  onEdit,
  onDelete,
}: {
  t: Translator;
  isDeleting: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className="h-8 rounded-md border px-2 text-xs"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        disabled={isDeleting}
        onClick={onEdit}
      >
        {t("categories.actions.edit")}
      </button>
      <button
        type="button"
        className="h-8 rounded-md border border-red-500/55 bg-red-500/12 px-2 text-xs font-semibold text-red-700 transition-colors hover:bg-red-500/20 disabled:opacity-60 dark:border-red-300/70 dark:bg-red-500/30 dark:text-red-100 dark:hover:bg-red-500/40"
        disabled={isDeleting}
        onClick={onDelete}
      >
        {isDeleting ? t("loading") : t("categories.actions.delete")}
      </button>
    </div>
  );
}
