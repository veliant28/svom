"use client";

import { Briefcase, Headset, ShieldCheck, UserRound, UsersRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";

const SYSTEM_PREFIX = "Backoffice Role:";

type SystemRoleCode = "administrator" | "manager" | "operator" | "user";

function resolveSystemRole(groupName: string): SystemRoleCode | null {
  const normalized = String(groupName || "").trim();
  if (!normalized.startsWith(SYSTEM_PREFIX)) {
    return null;
  }

  const rawRole = normalized.slice(SYSTEM_PREFIX.length).trim().toLowerCase();
  if (rawRole === "administrator" || rawRole === "manager" || rawRole === "operator" || rawRole === "user") {
    return rawRole;
  }
  return null;
}

function resolveRoleVisual(role: SystemRoleCode): {
  tone: BackofficeStatusChipTone;
  icon: LucideIcon;
} {
  if (role === "administrator") {
    return { tone: "red", icon: ShieldCheck };
  }
  if (role === "manager") {
    return { tone: "blue", icon: Briefcase };
  }
  if (role === "operator") {
    return { tone: "orange", icon: Headset };
  }
  return { tone: "gray", icon: UserRound };
}

export function RoleGroupBadge({
  groupName,
  className = "",
  forceDark = false,
}: {
  groupName: string;
  className?: string;
  forceDark?: boolean;
}) {
  const t = useTranslations("backoffice.common");
  const darkToneByRole: Record<SystemRoleCode, string> = {
    administrator: "!border-red-300/85 !bg-red-700/55 !text-red-50",
    manager: "!border-blue-300/85 !bg-blue-700/55 !text-blue-50",
    operator: "!border-orange-300/85 !bg-orange-700/55 !text-orange-50",
    user: "!border-zinc-300/85 !bg-zinc-700/55 !text-zinc-50",
  };
  const darkToneCustom = "!border-slate-300/85 !bg-slate-700/55 !text-slate-50";

  const role = resolveSystemRole(groupName);
  if (role) {
    const visual = resolveRoleVisual(role);
    const forceToneClass = forceDark ? darkToneByRole[role] : "";
    return (
      <BackofficeStatusChip tone={visual.tone} icon={visual.icon} className={`${forceToneClass} ${className}`.trim()}>
        {t(`rbac.roles.values.${role}`)}
      </BackofficeStatusChip>
    );
  }

  const forceToneClass = forceDark ? darkToneCustom : "";
  return (
    <BackofficeStatusChip tone="info" icon={UsersRound} className={`${forceToneClass} ${className}`.trim()}>
      {groupName || "-"}
    </BackofficeStatusChip>
  );
}
