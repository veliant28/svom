import { CheckCircle2, XCircle } from "lucide-react";

import { CategoryRowActions } from "@/features/backoffice/components/categories/category-row-actions";
import type { BackofficeColumn } from "@/features/backoffice/components/table/backoffice-table";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function createCategoryColumns({
  t,
  locale,
  deletingCategoryId,
  getDisplayName,
  getDisplayParentName,
  onEdit,
  onDelete,
}: {
  t: Translator;
  locale: string;
  deletingCategoryId: string | null;
  getDisplayName: (category: BackofficeCatalogCategory, locale: string) => string;
  getDisplayParentName: (category: BackofficeCatalogCategory) => string;
  onEdit: (category: BackofficeCatalogCategory) => void;
  onDelete: (category: BackofficeCatalogCategory) => void;
}): Array<BackofficeColumn<BackofficeCatalogCategory>> {
  return [
    {
      key: "name",
      label: t("categories.table.columns.name"),
      render: (item) => (
        <div>
          <p className="font-semibold">{getDisplayName(item, locale)}</p>
          <p className="text-xs" style={{ color: "var(--muted)" }}>{getDisplayParentName(item) || t("categories.table.rootLabel")}</p>
        </div>
      ),
    },
    {
      key: "status",
      label: t("categories.table.columns.status"),
      render: (item) => (
        <BackofficeStatusChip tone={item.is_active ? "success" : "gray"} icon={item.is_active ? CheckCircle2 : XCircle}>
          {item.is_active ? t("statuses.active") : t("statuses.inactive")}
        </BackofficeStatusChip>
      ),
    },
    { key: "updated", label: t("categories.table.columns.updated"), render: (item) => formatBackofficeDate(item.updated_at) },
    {
      key: "actions",
      label: t("categories.table.columns.actions"),
      render: (item) => (
        <CategoryRowActions
          t={t}
          isDeleting={deletingCategoryId === item.id}
          onEdit={() => onEdit(item)}
          onDelete={() => onDelete(item)}
        />
      ),
    },
  ];
}
