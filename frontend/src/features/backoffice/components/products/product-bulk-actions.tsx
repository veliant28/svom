import type { RefObject } from "react";
import { ListChecks } from "lucide-react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ProductBulkActions({
  bulkActionsRef,
  bulkActionsOpen,
  selectedCount,
  runningAction,
  onToggle,
  onOpenMoveCategoryModal,
  onReindex,
  onOpenDeleteModal,
  t,
}: {
  bulkActionsRef: RefObject<HTMLDivElement | null>;
  bulkActionsOpen: boolean;
  selectedCount: number;
  runningAction: "move_category" | "reindex" | "delete" | null;
  onToggle: () => void;
  onOpenMoveCategoryModal: () => void;
  onReindex: () => void;
  onOpenDeleteModal: () => void;
  t: Translator;
}) {
  return (
    <div ref={bulkActionsRef} className="relative shrink-0">
      <BackofficeTooltip content={t("products.tooltips.bulkActions")} placement="top" tooltipClassName="whitespace-nowrap">
        <button
          type="button"
          aria-label={t("products.actions.bulkActions")}
          aria-haspopup="menu"
          aria-expanded={bulkActionsOpen}
          className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          onClick={onToggle}
        >
          <ListChecks size={16} />
        </button>
      </BackofficeTooltip>
      {bulkActionsOpen ? (
        <div
          role="menu"
          className="absolute left-0 top-full z-30 mt-1 min-w-[240px] rounded-lg border p-1.5 shadow-xl"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <button
            type="button"
            role="menuitem"
            disabled={!selectedCount || Boolean(runningAction)}
            className="flex h-10 w-full items-center rounded-md px-3 text-left text-sm font-normal leading-5 text-slate-900 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 disabled:opacity-50"
            onClick={onOpenMoveCategoryModal}
          >
            {runningAction === "move_category" ? t("loading") : t("products.actions.bulkMoveCategory")}
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={!selectedCount || Boolean(runningAction)}
            className="flex h-10 w-full items-center rounded-md px-3 text-left text-sm font-normal leading-5 text-slate-900 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 disabled:opacity-50"
            onClick={onReindex}
          >
            {runningAction === "reindex" ? t("loading") : t("products.actions.bulkReindex")}
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={!selectedCount || Boolean(runningAction)}
            className="flex h-10 w-full items-center rounded-md px-3 text-left text-sm font-normal leading-5 text-slate-900 hover:bg-red-50 hover:text-red-700 dark:text-slate-100 dark:hover:bg-red-950/35 dark:hover:text-red-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 disabled:opacity-50"
            onClick={onOpenDeleteModal}
          >
            {runningAction === "delete" ? t("loading") : t("products.actions.bulkDelete")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
