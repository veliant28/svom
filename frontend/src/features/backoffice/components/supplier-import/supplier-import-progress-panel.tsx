import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { formatBackofficeDate, formatSupplierError } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeSupplierPriceList, BackofficeSupplierWorkspace } from "@/features/backoffice/types/suppliers.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierImportProgressPanel({
  t,
  tErrors,
  latestPriceList,
  latestDownloaded,
  latestImported,
  latestErrored,
  workspace,
  isUtr,
  cooldownCanRun,
  cooldownSecondsLeft,
}: {
  t: Translator;
  tErrors: Translator;
  latestPriceList?: BackofficeSupplierPriceList;
  latestDownloaded?: BackofficeSupplierPriceList;
  latestImported?: BackofficeSupplierPriceList;
  latestErrored?: BackofficeSupplierPriceList;
  workspace: BackofficeSupplierWorkspace;
  isUtr: boolean;
  cooldownCanRun: boolean;
  cooldownSecondsLeft: number;
}) {
  return (
    <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">{t("priceLifecycle.state.title")}</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.subtitle")}</p>
        </div>
        <StatusChip
          status={latestPriceList?.status || "pending"}
          countdownSeconds={latestPriceList?.generation_wait_seconds}
        />
      </div>

      <div className="mt-3 overflow-hidden rounded-xl border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
        <div className="grid gap-1.5 px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center">
          <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.lastRequestStatus")}</p>
          <p className="text-sm font-semibold">
            {latestPriceList ? (
              <StatusChip
                status={latestPriceList.status}
                countdownSeconds={latestPriceList.generation_wait_seconds}
              />
            ) : "-"}
          </p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
          <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.generation")}</p>
          <p className="text-sm font-semibold">
            {latestPriceList?.status === "generating"
              ? t("priceLifecycle.state.generatingWait", { seconds: latestPriceList.generation_wait_seconds })
              : t("priceLifecycle.state.generationDone")}
          </p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
          <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.downloadAvailable")}</p>
          <p className="text-sm font-semibold">
            {latestPriceList?.download_available ? t("priceLifecycle.state.yes") : t("priceLifecycle.state.no")}
          </p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
          <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.lastDownloaded")}</p>
          <p className="text-sm font-semibold">{formatBackofficeDate(latestDownloaded?.downloaded_at)}</p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
          <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.lastImported")}</p>
          <p className="text-sm font-semibold">{formatBackofficeDate(latestImported?.imported_at)}</p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
          <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>
            {isUtr ? t("priceLifecycle.state.cooldownUtr") : t("priceLifecycle.state.cooldownNotApplicableLabel")}
          </p>
          <p className="text-sm font-semibold">
            {isUtr
              ? (cooldownCanRun
                ? t("priceLifecycle.state.cooldownReady")
                : t("priceLifecycle.state.cooldownWait", { seconds: cooldownSecondsLeft }))
              : t("priceLifecycle.state.cooldownNotApplicableValue")}
          </p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[12rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
          <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>{t("priceLifecycle.state.lastError")}</p>
          <p className="text-sm font-semibold">
            {formatSupplierError(
              latestErrored?.last_error_message || workspace.import.last_import_error_message,
              tErrors("actions.failed"),
            )}
          </p>
        </div>
      </div>
    </article>
  );
}
