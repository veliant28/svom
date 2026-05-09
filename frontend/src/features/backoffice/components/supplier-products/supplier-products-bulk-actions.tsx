import type { RefObject } from "react";
import { ListChecks } from "lucide-react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierProductsBulkActions({
  bulkActionsRef,
  bulkActionsOpen,
  selectedCount,
  isPublishing,
  onToggle,
  onPublishSelected,
  t,
  tCommon,
}: {
  bulkActionsRef: RefObject<HTMLDivElement | null>;
  bulkActionsOpen: boolean;
  selectedCount: number;
  isPublishing: boolean;
  onToggle: () => void;
  onPublishSelected: () => void;
  t: Translator;
  tCommon: Translator;
}) {
  return (
    <div ref={bulkActionsRef} className="relative shrink-0">
      <BackofficeTooltip content={t("productsPage.tooltips.bulkActions")} placement="top" tooltipClassName="whitespace-nowrap">
        <button
          type="button"
          aria-label={t("productsPage.actions.bulkActions")}
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
          className="absolute left-0 top-full z-30 mt-1 min-w-[220px] rounded-lg border p-1.5 shadow-xl"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <button
            type="button"
            role="menuitem"
            disabled={!selectedCount || isPublishing}
            className="flex h-10 w-full items-center rounded-md px-3 text-left text-sm font-normal leading-5 text-slate-900 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 disabled:opacity-50"
            onClick={onPublishSelected}
          >
            {isPublishing ? tCommon("loading") : t("productsPage.actions.publishSelected")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
