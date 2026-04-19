import { BadgeDollarSign, RefreshCw } from "lucide-react";

import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { Link } from "@/i18n/navigation";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ProductsToolbar({
  t,
  onRefresh,
}: {
  t: Translator;
  onRefresh: () => void;
}) {
  return (
    <PageHeader
      title={t("products.title")}
      description={t("products.subtitle")}
      actionsBeforeLogout={(
        <button
          type="button"
          className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          onClick={onRefresh}
        >
          <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
          {t("products.actions.refresh")}
        </button>
      )}
      actions={(
        <div className="flex flex-wrap items-center gap-2">
          <BackofficeTooltip
            content={t("products.tooltips.openPricing")}
            placement="top"
            align="center"
            wrapperClassName="inline-flex"
            tooltipClassName="whitespace-nowrap"
          >
            <Link
              href="/backoffice/pricing"
              className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <BadgeDollarSign size={16} />
              {t("products.actions.pricing")}
            </Link>
          </BackofficeTooltip>
        </div>
      )}
    />
  );
}
