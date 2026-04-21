import { Pencil, Trash2 } from "lucide-react";

import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ProductRowActions({
  deleting,
  onEdit,
  onDelete,
  t,
}: {
  deleting: boolean;
  onEdit: () => void;
  onDelete: () => void;
  t: Translator;
}) {
  return (
    <div className="flex items-center gap-1.5 whitespace-nowrap">
      <ActionIconButton
        label={t("products.tooltips.actionEdit")}
        icon={Pencil}
        align="start"
        onClick={onEdit}
      />
      <ActionIconButton
        label={deleting ? t("loading") : t("products.tooltips.actionDelete")}
        icon={Trash2}
        tone="danger"
        align="start"
        disabled={deleting}
        onClick={onDelete}
      />
    </div>
  );
}
