import { useMemo } from "react";
import { RefreshCw } from "lucide-react";

import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { createSupplierImportColumns } from "@/features/backoffice/lib/supplier-import/supplier-import-columns";
import type { BackofficeSupplierPriceList } from "@/features/backoffice/types/suppliers.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierImportRunsTable({
  t,
  rows,
  isLoading,
  error,
  tokenReady,
  cooldownCanRun,
  onRefresh,
  onRowRequest,
  onRowDownload,
  onRowImport,
  onRowDelete,
}: {
  t: Translator;
  rows: BackofficeSupplierPriceList[];
  isLoading: boolean;
  error: string | null;
  tokenReady: boolean;
  cooldownCanRun: boolean;
  onRefresh: () => void;
  onRowRequest: (item: BackofficeSupplierPriceList) => void;
  onRowDownload: (item: BackofficeSupplierPriceList) => void;
  onRowImport: (item: BackofficeSupplierPriceList) => void;
  onRowDelete: (item: BackofficeSupplierPriceList) => void;
}) {
  const columns = useMemo(
    () => createSupplierImportColumns({
      t,
      tokenReady,
      cooldownCanRun,
      onRowRequest,
      onRowDownload,
      onRowImport,
      onRowDelete,
    }),
    [cooldownCanRun, onRowDelete, onRowDownload, onRowImport, onRowRequest, t, tokenReady],
  );

  return (
    <section className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">{t("priceLifecycle.table.title")}</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("priceLifecycle.table.subtitle")}</p>
        </div>
        <button
          type="button"
          className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold disabled:cursor-not-allowed"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          onClick={onRefresh}
          disabled={isLoading}
        >
          <RefreshCw
            size={16}
            className="animate-spin"
            style={{ animationDuration: isLoading ? "0.9s" : "2.2s" }}
          />
          {t("actions.refreshAll")}
        </button>
      </div>

      <div className="mt-3">
        <AsyncState
          isLoading={isLoading}
          error={error}
          empty={!rows.length}
          emptyLabel={t("priceLifecycle.table.empty")}
        >
          <BackofficeTable
            emptyLabel={t("priceLifecycle.table.empty")}
            rows={rows}
            columns={columns}
          />
        </AsyncState>
      </div>
    </section>
  );
}
