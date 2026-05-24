import { Bot, ShieldAlert, ShieldCheck } from "lucide-react";

import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import type { SecurityActor, SecurityStatus, SecurityThreatLevel } from "@/features/backoffice/security/types/security.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

const STATUS_TONES: Record<SecurityStatus, "success" | "warning" | "error" | "info" | "gray" | "blue"> = {
  blocked: "error",
  suspicious: "warning",
  whitelisted: "success",
  unblocked: "info",
  expired: "gray",
  error: "error",
};

const THREAT_TONES: Record<SecurityThreatLevel, "success" | "warning" | "error" | "orange"> = {
  low: "success",
  medium: "warning",
  high: "orange",
  critical: "error",
};

const SOURCE_KIND_KEYS = new Set(["ipv4", "ipv6", "vpn", "proxy", "tor", "datacenter", "bot", "crawler", "user", "unknown"]);

export function SecurityStatusBadge({
  status,
  t,
  onClick,
}: {
  status: SecurityStatus;
  t: Translator;
  onClick?: () => void;
}) {
  const chip = (
    <StatusChip tone={STATUS_TONES[status] ?? "gray"} icon={status === "whitelisted" ? ShieldCheck : ShieldAlert}>
      {t(`status.${status}`)}
    </StatusChip>
  );

  if (!onClick || status !== "blocked") {
    return chip;
  }
  return (
    <button type="button" className="inline-flex" onClick={onClick} aria-label={t("actions.history")}>
      {chip}
    </button>
  );
}

export function SecurityThreatBadge({ level, t }: { level: SecurityThreatLevel; t: Translator }) {
  return (
    <StatusChip tone={THREAT_TONES[level] ?? "gray"} icon={ShieldAlert}>
      {t(`threat.${level}`)}
    </StatusChip>
  );
}

export function SourceKindBadges({
  actor,
  t,
  className = "",
  primaryOnly = false,
}: {
  actor: SecurityActor;
  t: Translator;
  className?: string;
  primaryOnly?: boolean;
}) {
  const sourceFlags = primaryOnly ? [actor.source_kind] : [actor.source_kind, ...actor.source_flags];
  const flags = sourceFlags
    .map((flag) => String(flag || "").toLowerCase())
    .filter((flag, index, list) => SOURCE_KIND_KEYS.has(flag) && list.indexOf(flag) === index);
  return (
    <div className={`flex flex-wrap gap-1 ${className}`}>
      {flags.map((flag) => (
        <StatusChip key={flag} tone="gray" icon={flag === "bot" ? Bot : undefined} className="px-1.5 py-0.5 text-[11px]">
          {t(`sourceKind.${flag}`)}
        </StatusChip>
      ))}
    </div>
  );
}
