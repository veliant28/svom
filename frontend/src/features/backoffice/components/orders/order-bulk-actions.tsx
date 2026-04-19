import type { RefObject } from "react";
import { ListChecks } from "lucide-react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function OrderBulkActions({
  bulkActionsRef,
  bulkActionsOpen,
  selectedCount,
  running,
  onToggle,
  onDelete,
  t,
}: {
  bulkActionsRef: RefObject<HTMLDivElement | null>;
  bulkActionsOpen: boolean;
  selectedCount: number;
  running: boolean;
  onToggle: () => void;
  onDelete: () => void;
  t: Translator;
}) {
  return (
    <div ref={bulkActionsRef} className="relative shrink-0">
      <BackofficeTooltip content={t("orders.tooltips.bulkActions")} placement="top" tooltipClassName="whitespace-nowrap">
        <button
          type="button"
          aria-label={t("orders.actions.bulkActions")}
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
          className="absolute left-0 top-full z-30 mt-1 min-w-[260px] rounded-lg border p-1.5 shadow-xl"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <p className="px-3 pb-1 text-xs" style={{ color: "var(--muted)" }}>
            {t("orders.bulk.selected", { count: selectedCount })}
          </p>
          <button
            type="button"
            role="menuitem"
            disabled={running || selectedCount <= 0}
            className="flex h-10 w-full items-center rounded-md px-3 text-left text-sm font-normal leading-5 text-slate-900 hover:bg-red-50 hover:text-red-700 dark:text-slate-100 dark:hover:bg-red-950/35 dark:hover:text-red-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 disabled:opacity-50"
            onClick={onDelete}
          >
            {running ? t("loading") : t("orders.actions.bulkDelete")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
