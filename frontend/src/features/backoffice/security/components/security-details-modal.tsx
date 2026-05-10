"use client";

import { History, ShieldCheck, Unlock, X } from "lucide-react";
import { createPortal } from "react-dom";

import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { SecurityStatusBadge, SecurityThreatBadge, SourceKindBadges } from "@/features/backoffice/security/components/security-badges";
import { SecurityBlockTimer } from "@/features/backoffice/security/components/security-timer";
import type { SecurityActor, SecurityActorDetail, SecurityBlock } from "@/features/backoffice/security/types/security.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function InfoRow({ label, value, emptyLabel }: { label: string; value: string | number | null | undefined; emptyLabel: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>{label}</p>
      <p className="mt-0.5 truncate text-sm">{value || emptyLabel}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <p className="mb-3 text-sm font-semibold">{title}</p>
      {children}
    </section>
  );
}

function formatDate(value: string | null, locale: string): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function SecurityDetailsModal({
  actor,
  detail,
  locale,
  t,
  onClose,
  onHistory,
  onRelease,
  onReblock,
  onWhitelist,
}: {
  actor: SecurityActor | null;
  detail: SecurityActorDetail | null;
  locale: string;
  t: Translator;
  onClose: () => void;
  onHistory: (actor: SecurityActor) => void;
  onRelease: (block: SecurityBlock) => void;
  onReblock: (actor: SecurityActor) => void;
  onWhitelist: (actor: SecurityActor) => void;
}) {
  if (!actor || typeof document === "undefined") {
    return null;
  }
  const activeBlock = detail?.active_block ?? actor.active_block;
  const metadata = actor.metadata || {};
  const reasons = Array.isArray(metadata.threat_reasons) ? metadata.threat_reasons.map(String) : [];
  const emptyLabel = t("empty.value");

  return createPortal(
    <div className="fixed inset-0 z-[1420] flex items-center justify-center bg-black/45 px-3 py-4" onClick={onClose}>
      <div className="w-full max-w-6xl overflow-hidden rounded-xl border shadow-2xl" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }} onClick={(event) => event.stopPropagation()}>
        <header className="flex flex-wrap items-start justify-between gap-3 border-b px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <SourceKindBadges actor={actor} t={t} primaryOnly className="shrink-0" />
              <p className="truncate text-base font-semibold">{actor.source_ip || actor.source_identifier}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <SecurityStatusBadge status={actor.status} t={t} />
            <SecurityThreatBadge level={actor.threat_level} t={t} />
            <SecurityBlockTimer block={activeBlock} t={t} />
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border transition-colors"
              aria-label={activeBlock ? t("actions.release") : t("actions.reblock")}
              style={{
                borderColor: activeBlock ? "#16a34a" : "var(--border)",
                backgroundColor: activeBlock ? "#16a34a" : "var(--surface)",
                color: activeBlock ? "#ffffff" : "var(--text)",
              }}
              onClick={() => (activeBlock ? onRelease(activeBlock) : onReblock(actor))}
            >
              <Unlock className="size-4" />
            </button>
            <ActionIconButton label={t("actions.whitelist")} icon={ShieldCheck} onClick={() => onWhitelist(actor)} />
            <ActionIconButton label={t("actions.history")} icon={History} onClick={() => onHistory(actor)} />
            <button type="button" className="inline-flex h-8 w-8 items-center justify-center rounded-md border" style={{ borderColor: "var(--border)" }} aria-label={t("actions.close")} onClick={onClose}>
              <X className="size-4" />
            </button>
          </div>
        </header>
        <div className="max-h-[90vh] overflow-y-auto p-4">
          <div className="grid gap-3 xl:grid-cols-2">
            <Section title={t("modals.details.sections.main")}>
              <div className="grid grid-cols-2 gap-3">
                <InfoRow label={t("fields.ip")} value={actor.source_ip || actor.source_identifier} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.ipType")} value={t(`sourceKind.${actor.source_kind}`)} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.userAgent")} value={String(metadata.user_agent || "")} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.fingerprint")} value={String(metadata.fingerprint || "")} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.session")} value={String(metadata.session_key || "")} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.firstSeen")} value={formatDate(actor.first_seen_at, locale)} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.lastSeen")} value={formatDate(actor.last_seen_at, locale)} emptyLabel={emptyLabel} />
              </div>
            </Section>

            <Section title={t("modals.details.sections.client")}>
              <div className="grid grid-cols-2 gap-3">
                <InfoRow label={t("fields.login")} value={actor.login_snapshot || t("table.anonymous")} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.email")} value={actor.email_snapshot || actor.user_label} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.phone")} value={String(metadata.phone || "")} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.userId")} value={actor.user} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.accountStatus")} value={String(metadata.account_status || "")} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.roles")} value={Array.isArray(metadata.roles) ? metadata.roles.join(", ") : ""} emptyLabel={emptyLabel} />
              </div>
            </Section>

            <Section title={t("modals.details.sections.threat")}>
              <div className="grid grid-cols-2 gap-3">
                <InfoRow label={t("fields.threat")} value={t(`threat.${actor.threat_level}`)} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.threatScore")} value={actor.threat_score} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.blockCount")} value={actor.block_count} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.blockType")} value={activeBlock?.is_automatic ? t("block.automatic") : t("block.manual")} emptyLabel={emptyLabel} />
              </div>
              <ul className="mt-3 grid gap-1 text-sm" style={{ color: "var(--muted)" }}>
                {(reasons.length ? reasons : [t("empty.reasons")]).map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
            </Section>

            <Section title={t("modals.details.sections.block")}>
              <div className="grid grid-cols-2 gap-3">
                <InfoRow label={t("fields.status")} value={activeBlock ? t(`block.status.${activeBlock.status}`) : t("block.noActive")} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.reason")} value={activeBlock?.reason} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.blockMode")} value={activeBlock ? t(`block.mode.${activeBlock.block_mode}`) : emptyLabel} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.blockedAt")} value={formatDate(activeBlock?.blocked_at ?? null, locale)} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.expiresAt")} value={activeBlock?.expires_at ? formatDate(activeBlock.expires_at, locale) : t("block.indefinite")} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.blockedBy")} value={activeBlock?.blocked_by_label || t("block.system")} emptyLabel={emptyLabel} />
                <InfoRow label={t("fields.comment")} value={activeBlock?.comment} emptyLabel={emptyLabel} />
              </div>
            </Section>
          </div>

          <div className="mt-3 grid gap-3 xl:grid-cols-3">
            <Section title={t("modals.details.sections.activity")}>
              <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                {Object.entries(detail?.activity_summary ?? {}).map(([key, value]) => (
                  <article key={key} className="rounded-lg border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                    <p className="text-[11px] font-semibold" style={{ color: "var(--muted)" }}>{t(`activity.${key}`)}</p>
                    <p className="mt-1 text-lg font-semibold">{value}</p>
                  </article>
                ))}
              </div>
            </Section>

            <Section title={t("modals.details.sections.recentEvents")}>
              <div className="grid gap-2">
                {(detail?.recent_events ?? []).slice(0, 6).map((event) => (
                  <div key={event.id} className="grid grid-cols-[1fr_auto] gap-2 text-sm">
                    <span className="truncate">{t(`eventTypes.${event.event_type}`)}</span>
                    <span style={{ color: "var(--muted)" }}>{formatDate(event.created_at, locale)}</span>
                  </div>
                ))}
              </div>
            </Section>

            <Section title={t("modals.details.sections.endpoints")}>
              <div className="grid gap-2">
                {(detail?.top_endpoints ?? []).slice(0, 8).map((row) => (
                  <div key={`${row.endpoint}:${row.last_status_code}`} className="grid grid-cols-[1fr_auto_auto] gap-2 text-sm">
                    <span className="truncate">{row.endpoint}</span>
                    <strong>{row.requests}</strong>
                    <span>{row.last_status_code || emptyLabel}</span>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
