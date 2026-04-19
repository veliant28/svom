import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierProductsRowActions({
  status,
  mappedCategoryPath,
  expanded,
  onOpen,
  t,
}: {
  status: string;
  mappedCategoryPath: string;
  expanded: boolean;
  onOpen: () => void;
  t: Translator;
}) {
  return (
    <button
      type="button"
      className="inline-flex rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
      style={{ cursor: "pointer" }}
      onClick={onOpen}
      aria-label={t("productsPage.categoryMapping.openBadgeAria")}
      aria-haspopup="dialog"
      aria-expanded={expanded}
      title={mappedCategoryPath || t("productsPage.categoryMapping.states.notMapped")}
    >
      <StatusChip status={status || "unmapped"} />
    </button>
  );
}
