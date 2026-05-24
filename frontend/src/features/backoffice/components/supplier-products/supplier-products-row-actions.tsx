import { StatusChip, type StatusChipTone } from "@/features/backoffice/components/widgets/status-chip";
import { AlertTriangle, CheckCircle2, MinusCircle, UserCheck, type LucideIcon } from "lucide-react";

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
  const normalizedStatus = String(status || "unmapped").trim().toLowerCase();
  const toneByStatus: Record<string, StatusChipTone> = {
    auto_mapped: "success",
    manual_mapped: "blue",
    needs_review: "warning",
    unmapped: "gray",
  };
  const iconByStatus: Record<string, LucideIcon> = {
    auto_mapped: CheckCircle2,
    manual_mapped: UserCheck,
    needs_review: AlertTriangle,
    unmapped: MinusCircle,
  };
  const shortLabelByStatus: Record<string, string> = {
    auto_mapped: t("productsPage.review.statusesShort.auto_mapped"),
    manual_mapped: t("productsPage.review.statusesShort.manual_mapped"),
    needs_review: t("productsPage.review.statusesShort.needs_review"),
    unmapped: t("productsPage.review.statusesShort.unmapped"),
  };
  const fullLabelByStatus: Record<string, string> = {
    auto_mapped: t("productsPage.review.statuses.auto_mapped"),
    manual_mapped: t("productsPage.review.statuses.manual_mapped"),
    needs_review: t("productsPage.review.statuses.needs_review"),
    unmapped: t("productsPage.review.statuses.unmapped"),
  };
  const shortLabel = shortLabelByStatus[normalizedStatus] || t("productsPage.review.statusesShort.unmapped");
  const fullLabel = fullLabelByStatus[normalizedStatus] || t("productsPage.review.statuses.unmapped");
  const tone = toneByStatus[normalizedStatus] || "gray";
  const Icon = iconByStatus[normalizedStatus] || MinusCircle;

  return (
    <button
      type="button"
      className="inline-flex rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
      style={{ cursor: "pointer" }}
      onClick={onOpen}
      aria-label={t("productsPage.categoryMapping.openBadgeAria")}
      aria-haspopup="dialog"
      aria-expanded={expanded}
      title={`${fullLabel}${mappedCategoryPath ? ` • ${mappedCategoryPath}` : ""}`}
    >
      <StatusChip tone={tone} icon={Icon}>
        {shortLabel}
      </StatusChip>
    </button>
  );
}
