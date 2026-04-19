import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { SupplierScheduleActions } from "@/features/backoffice/components/suppliers/supplier-actions";
import { suppliersSchedulesEmptyLabel } from "@/features/backoffice/components/suppliers/suppliers-empty-state";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import type { BackofficeImportSource } from "@/features/backoffice/types/imports.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SuppliersSchedulesList({
  tCommon,
  schedulesLoading,
  schedulesError,
  rows,
  onToggleAutoImport,
  onSaveDefaultCron,
}: {
  tCommon: Translator;
  schedulesLoading: boolean;
  schedulesError: string | null;
  rows: BackofficeImportSource[];
  onToggleAutoImport: (item: BackofficeImportSource) => void;
  onSaveDefaultCron: (item: BackofficeImportSource) => void;
}) {
  const emptyLabel = suppliersSchedulesEmptyLabel(tCommon);

  return (
    <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <h2 className="text-sm font-semibold">{tCommon("importSchedules.title")}</h2>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {tCommon("importSchedules.subtitle")}
      </p>

      <div className="mt-3">
        <AsyncState
          isLoading={schedulesLoading}
          error={schedulesError}
          empty={!rows.length}
          emptyLabel={emptyLabel}
        >
          <BackofficeTable
            emptyLabel={emptyLabel}
            rows={rows}
            columns={[
              {
                key: "source",
                label: tCommon("importSchedules.table.columns.source"),
                render: (item) => (
                  <div>
                    <p className="font-semibold">{item.name}</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>
                      {item.code} / {item.supplier_code}
                    </p>
                  </div>
                ),
              },
              {
                key: "enabled",
                label: tCommon("importSchedules.table.columns.enabled"),
                render: (item) => <StatusChip status={item.is_auto_import_enabled ? "enabled" : "disabled"} />,
              },
              {
                key: "cron",
                label: tCommon("importSchedules.table.columns.cron"),
                render: (item) => (
                  <div>
                    <p>{item.schedule_cron || "-"}</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>
                      {item.schedule_timezone}
                    </p>
                  </div>
                ),
              },
              {
                key: "nextRun",
                label: tCommon("importSchedules.table.columns.nextRun"),
                render: (item) => item.next_run || "-",
              },
              {
                key: "lastResult",
                label: tCommon("importSchedules.table.columns.lastResult"),
                render: (item) =>
                  item.last_run ? (
                    <div>
                      <StatusChip status={item.last_run.status} />
                      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                        {tCommon("importSchedules.table.lastRunSummary", {
                          rows: item.last_run.processed_rows,
                          errors: item.last_run.errors_count,
                        })}
                      </p>
                    </div>
                  ) : (
                    "-"
                  ),
              },
              {
                key: "actions",
                label: tCommon("importSchedules.table.columns.actions"),
                render: (item) => (
                  <SupplierScheduleActions
                    item={item}
                    tCommon={tCommon}
                    onToggleAutoImport={onToggleAutoImport}
                    onSaveDefaultCron={onSaveDefaultCron}
                  />
                ),
              },
            ]}
          />
        </AsyncState>
      </div>
    </article>
  );
}

export function SuppliersFooter({
  t,
  suppliersCount,
}: {
  t: Translator;
  suppliersCount: number;
}) {
  return (
    <p className="text-xs" style={{ color: "var(--muted)" }}>
      {t("footer.availableSuppliers", { count: suppliersCount })}
    </p>
  );
}
