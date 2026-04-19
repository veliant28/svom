import type { BackofficeImportSource } from "@/features/backoffice/types/imports.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierAuthorizationActions({
  tAuth,
  onSaveSettings,
  onObtainToken,
  onRefreshToken,
  onCheckConnection,
}: {
  tAuth: Translator;
  onSaveSettings: () => void;
  onObtainToken: () => void;
  onRefreshToken: () => void;
  onCheckConnection: () => void;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <button
        type="button"
        className="h-10 rounded-md border px-3 text-sm font-semibold"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        onClick={onSaveSettings}
      >
        {tAuth("actions.saveSettings")}
      </button>
      <button
        type="button"
        className="h-10 rounded-md border px-3 text-sm font-semibold"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        onClick={onObtainToken}
      >
        {tAuth("actions.obtainToken")}
      </button>
      <button
        type="button"
        className="h-10 rounded-md border px-3 text-sm font-semibold"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        onClick={onRefreshToken}
      >
        {tAuth("actions.refreshToken")}
      </button>
      <button
        type="button"
        className="h-10 rounded-md border px-3 text-sm font-semibold"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        onClick={onCheckConnection}
      >
        {tAuth("actions.checkConnection")}
      </button>
    </div>
  );
}

export function SupplierScheduleActions({
  item,
  tCommon,
  onToggleAutoImport,
  onSaveDefaultCron,
}: {
  item: BackofficeImportSource;
  tCommon: Translator;
  onToggleAutoImport: (item: BackofficeImportSource) => void;
  onSaveDefaultCron: (item: BackofficeImportSource) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      <button
        type="button"
        className="h-8 rounded-md border px-2 text-xs"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        onClick={() => onToggleAutoImport(item)}
      >
        {item.is_auto_import_enabled
          ? tCommon("importSchedules.actions.disable")
          : tCommon("importSchedules.actions.enable")}
      </button>
      <button
        type="button"
        className="h-8 rounded-md border px-2 text-xs"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        onClick={() => onSaveDefaultCron(item)}
      >
        {tCommon("importSchedules.actions.saveDefaults")}
      </button>
    </div>
  );
}
