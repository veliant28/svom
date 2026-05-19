"use client";

import { Check, Copy, Globe2, LoaderCircle } from "lucide-react";

import type { BackofficeAutoDbRemoteState } from "@/features/backoffice/types/integration-center.types";

type AutoDbRemoteField = "remote_host" | "remote_port" | "remote_database" | "remote_user" | "remote_password" | "image_base_url";
type Translator = (key: string, values?: Record<string, string | number>) => string;

export function AutoDbRemoteCard({
  t,
  autodbRemote,
  autodbDraft,
  copiedField,
  updatingAutoDbFields,
  isTestingAutoDbConnection,
  onDraftChange,
  onCommit,
  onCopyField,
  onTestConnection,
}: {
  t: Translator;
  autodbRemote: BackofficeAutoDbRemoteState | null;
  autodbDraft: Record<AutoDbRemoteField, string>;
  copiedField: AutoDbRemoteField | "google_api_key" | null;
  updatingAutoDbFields: Record<AutoDbRemoteField, boolean>;
  isTestingAutoDbConnection: boolean;
  onDraftChange: (field: AutoDbRemoteField, value: string) => void;
  onCommit: (field: AutoDbRemoteField) => void;
  onCopyField: (field: AutoDbRemoteField | "google_api_key", value: string) => void;
  onTestConnection: () => void;
}) {
  return (
    <article className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold">
        <Globe2 size={16} />
        <span>{t("integrationCenter.groups.autodbRemote")}</span>
      </p>
      {!autodbRemote?.has_schema ? (
        <p className="text-xs" style={{ color: "var(--muted)" }}>{t("integrationCenter.autodbRemote.schemaMissing")}</p>
      ) : (
        <div className="grid gap-2">
          {(
            [
              { key: "remote_host", type: "text", placeholder: t("integrationCenter.autodbRemote.placeholders.remoteHost"), label: t("integrationCenter.autodbRemote.fields.remoteHost"), copyValue: autodbDraft.remote_host || autodbRemote.remote_host },
              { key: "remote_port", type: "number", placeholder: t("integrationCenter.autodbRemote.placeholders.remotePort"), label: t("integrationCenter.autodbRemote.fields.remotePort"), copyValue: autodbDraft.remote_port || String(autodbRemote.remote_port) },
              { key: "remote_database", type: "text", placeholder: t("integrationCenter.autodbRemote.placeholders.remoteDatabase"), label: t("integrationCenter.autodbRemote.fields.remoteDatabase"), copyValue: autodbDraft.remote_database || autodbRemote.remote_database },
              { key: "image_base_url", type: "text", placeholder: t("integrationCenter.autodbRemote.placeholders.imageBaseUrl"), label: t("integrationCenter.autodbRemote.fields.imageBaseUrl"), copyValue: autodbDraft.image_base_url || autodbRemote.image_base_url },
            ] as const
          ).map((fieldMeta) => (
            <label key={fieldMeta.key} className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <span>{fieldMeta.label}</span>
              <span className="relative inline-flex w-full items-center">
                <input
                  type={fieldMeta.type}
                  min={fieldMeta.key === "remote_port" ? 1 : undefined}
                  value={autodbDraft[fieldMeta.key]}
                  onChange={(event) => onDraftChange(fieldMeta.key, event.target.value)}
                  onBlur={() => { onCommit(fieldMeta.key); }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      onCommit(fieldMeta.key);
                    }
                  }}
                  placeholder={fieldMeta.placeholder}
                  className="h-9 w-full rounded-md border px-2 pr-10"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                />
                <button
                  type="button"
                  className="absolute right-1 inline-flex h-7 w-7 items-center justify-center rounded-md border"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  aria-label={t("integrationCenter.actions.copy")}
                  onClick={() => { onCopyField(fieldMeta.key, fieldMeta.copyValue); }}
                >
                  {copiedField === fieldMeta.key ? <Check size={13} /> : <Copy size={13} />}
                </button>
                {updatingAutoDbFields[fieldMeta.key] ? <LoaderCircle size={14} className="animate-spin" /> : null}
              </span>
            </label>
          ))}

          <label className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <span>{t("integrationCenter.autodbRemote.fields.remoteUser")}</span>
            <span className="relative inline-flex w-full items-center">
              <input
                type="password"
                value={autodbDraft.remote_user}
                onChange={(event) => onDraftChange("remote_user", event.target.value)}
                onBlur={() => { onCommit("remote_user"); }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    onCommit("remote_user");
                  }
                }}
                placeholder={autodbRemote.remote_user_masked || t("integrationCenter.autodbRemote.placeholders.remoteUser")}
                className="h-9 w-full rounded-md border px-2 pr-10"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
              <button
                type="button"
                className="absolute right-1 inline-flex h-7 w-7 items-center justify-center rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                aria-label={t("integrationCenter.actions.copy")}
                onClick={() => { onCopyField("remote_user", autodbDraft.remote_user); }}
              >
                {copiedField === "remote_user" ? <Check size={13} /> : <Copy size={13} />}
              </button>
              {updatingAutoDbFields.remote_user ? <LoaderCircle size={14} className="animate-spin" /> : null}
            </span>
            <span style={{ color: "var(--muted)" }}>
              {autodbRemote.remote_user_masked
                ? t("integrationCenter.autodbRemote.masked.remoteUser", { value: autodbRemote.remote_user_masked })
                : t("integrationCenter.autodbRemote.empty.remoteUser")}
            </span>
          </label>

          <label className="flex cursor-pointer flex-col gap-1 rounded-md border px-2.5 py-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <span>{t("integrationCenter.autodbRemote.fields.remotePassword")}</span>
            <span className="relative inline-flex w-full items-center">
              <input
                type="password"
                value={autodbDraft.remote_password}
                onChange={(event) => onDraftChange("remote_password", event.target.value)}
                onBlur={() => { onCommit("remote_password"); }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    onCommit("remote_password");
                  }
                }}
                placeholder={autodbRemote.remote_password_masked || t("integrationCenter.autodbRemote.placeholders.remotePassword")}
                className="h-9 w-full rounded-md border px-2 pr-10"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              />
              <button
                type="button"
                className="absolute right-1 inline-flex h-7 w-7 items-center justify-center rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                aria-label={t("integrationCenter.actions.copy")}
                onClick={() => { onCopyField("remote_password", autodbDraft.remote_password); }}
              >
                {copiedField === "remote_password" ? <Check size={13} /> : <Copy size={13} />}
              </button>
              {updatingAutoDbFields.remote_password ? <LoaderCircle size={14} className="animate-spin" /> : null}
            </span>
            <span style={{ color: "var(--muted)" }}>
              {autodbRemote.remote_password_masked
                ? t("integrationCenter.autodbRemote.masked.remotePassword", { value: autodbRemote.remote_password_masked })
                : t("integrationCenter.autodbRemote.empty.remotePassword")}
            </span>
          </label>

          <button
            type="button"
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onTestConnection}
            disabled={isTestingAutoDbConnection}
          >
            {isTestingAutoDbConnection ? <LoaderCircle size={14} className="animate-spin" /> : null}
            <span>{t("integrationCenter.actions.testConnection")}</span>
          </button>
        </div>
      )}
    </article>
  );
}
