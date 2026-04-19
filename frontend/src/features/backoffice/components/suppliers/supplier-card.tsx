import { Clock3, KeyRound, Plug, RefreshCw } from "lucide-react";

import { SupplierAuthorizationActions } from "@/features/backoffice/components/suppliers/supplier-actions";
import { SupplierTokenCountdownBadge, SupplierTokenStateBadge } from "@/features/backoffice/components/suppliers/supplier-status-badges";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import { shouldShowSupplierFingerprint } from "@/features/backoffice/lib/suppliers/supplier-auth-utils";
import { maskedTokenView } from "@/features/backoffice/lib/suppliers/supplier-formatters";
import type { SupplierStatusTone } from "@/features/backoffice/lib/suppliers/supplier-status";
import type { BackofficeSupplierWorkspace } from "@/features/backoffice/types/suppliers.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierAuthorizationCard({
  tAuth,
  activeCode,
  login,
  password,
  fingerprint,
  isEnabled,
  onLoginChange,
  onPasswordChange,
  onFingerprintChange,
  onEnabledChange,
  onSaveSettings,
  onObtainToken,
  onRefreshToken,
  onCheckConnection,
}: {
  tAuth: Translator;
  activeCode: string;
  login: string;
  password: string;
  fingerprint: string;
  isEnabled: boolean;
  onLoginChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onFingerprintChange: (value: string) => void;
  onEnabledChange: (value: boolean) => void;
  onSaveSettings: () => void;
  onObtainToken: () => void;
  onRefreshToken: () => void;
  onCheckConnection: () => void;
}) {
  const showFingerprint = shouldShowSupplierFingerprint(activeCode);

  return (
    <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <h2 className="text-sm font-semibold">{tAuth("cards.authorization")}</h2>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{tAuth("subtitle")}</p>

      <div className="mt-3 max-w-xl space-y-3">
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>
              {tAuth("fields.login")}
            </span>
            <input
              value={login}
              onChange={(event) => onLoginChange(event.target.value)}
              className="h-10 rounded-md border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>
              {tAuth("fields.password")}
            </span>
            <input
              type="password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              className="h-10 rounded-md border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            />
          </label>
          {showFingerprint ? (
            <label className="grid gap-1 sm:col-span-2">
              <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>
                {tAuth("fields.fingerprint")}
              </span>
              <input
                value={fingerprint}
                onChange={(event) => onFingerprintChange(event.target.value)}
                className="h-10 rounded-md border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              />
            </label>
          ) : null}
        </div>

        <label className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(event) => onEnabledChange(event.target.checked)}
          />
          {tAuth("fields.enabled")}
        </label>

        <SupplierAuthorizationActions
          tAuth={tAuth}
          onSaveSettings={onSaveSettings}
          onObtainToken={onObtainToken}
          onRefreshToken={onRefreshToken}
          onCheckConnection={onCheckConnection}
        />
      </div>
    </article>
  );
}

export function SupplierConnectionStatusCard({
  tAuth,
  workspace,
  connectionLabel,
  tokenStateLabel,
  tokenCountdownLabel,
  accessTone,
}: {
  tAuth: Translator;
  workspace: BackofficeSupplierWorkspace;
  connectionLabel: string;
  tokenStateLabel: string;
  tokenCountdownLabel: string;
  accessTone: SupplierStatusTone;
}) {
  return (
    <article className="rounded-2xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">{tAuth("cards.status")}</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{tAuth("status.subtitle")}</p>
        </div>
        <SupplierTokenStateBadge tone={accessTone} label={tokenStateLabel} />
      </div>

      <div className="mt-3 overflow-hidden rounded-xl border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
        <div className="grid gap-1.5 px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)] sm:items-center">
          <p className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--muted)" }}>
            <Plug size={18} />
            {tAuth("status.connection")}
          </p>
          <p className="text-sm font-semibold">{connectionLabel}</p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
          <p className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--muted)" }}>
            <Clock3 size={18} />
            {tAuth("status.accessExpires")}
          </p>
          <p className="text-sm font-semibold">{formatBackofficeDate(workspace.connection.access_token_expires_at)}</p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
          <p className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--muted)" }}>
            <Clock3 size={18} />
            {tAuth("status.refreshExpires")}
          </p>
          <p className="text-sm font-semibold">{formatBackofficeDate(workspace.connection.refresh_token_expires_at)}</p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)] sm:items-center" style={{ borderTopColor: "var(--border)" }}>
          <p className="inline-flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--muted)" }}>
            <RefreshCw size={18} />
            {tAuth("status.lastRefresh")}
          </p>
          <p className="text-sm font-semibold">{formatBackofficeDate(workspace.connection.last_token_refresh_at)}</p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)]" style={{ borderTopColor: "var(--border)" }}>
          <p className="inline-flex items-center gap-2 text-xs font-semibold sm:mt-0.5" style={{ color: "var(--muted)" }}>
            <KeyRound size={18} />
            {tAuth("status.accessMasked")}
          </p>
          <p className="break-all font-mono text-sm font-semibold leading-5">{maskedTokenView(workspace.connection.access_token_masked)}</p>
        </div>
        <div className="grid gap-1.5 border-t px-3.5 py-2.5 sm:grid-cols-[14rem_minmax(0,1fr)]" style={{ borderTopColor: "var(--border)" }}>
          <p className="inline-flex items-center gap-2 text-xs font-semibold sm:mt-0.5" style={{ color: "var(--muted)" }}>
            <KeyRound size={18} />
            {tAuth("status.refreshMasked")}
          </p>
          <p className="break-all font-mono text-sm font-semibold leading-5">{maskedTokenView(workspace.connection.refresh_token_masked)}</p>
        </div>
      </div>

      <div className="mt-2.5 flex justify-end">
        <SupplierTokenCountdownBadge tone={accessTone} label={tokenCountdownLabel} />
      </div>
    </article>
  );
}
