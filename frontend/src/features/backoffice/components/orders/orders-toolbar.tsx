import { RefreshCw } from "lucide-react";

import { PageHeader } from "@/features/backoffice/components/widgets/page-header";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function OrdersToolbar({
  t,
  onRefresh,
}: {
  t: Translator;
  onRefresh: () => void;
}) {
  return (
    <PageHeader
      title={t("orders.title")}
      description={t("orders.subtitle")}
      actionsBeforeLogout={(
        <button
          type="button"
          className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          onClick={onRefresh}
        >
          <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
          {t("orders.actions.refresh")}
        </button>
      )}
    />
  );
}
