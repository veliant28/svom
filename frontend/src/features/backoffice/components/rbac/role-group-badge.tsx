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
    return { tone: "black", icon: ShieldCheck };
  }
  if (role === "manager") {
    return { tone: "blue", icon: Briefcase };
  }
  if (role === "operator") {
    return { tone: "orange", icon: Headset };
  }
  return { tone: "gray", icon: UserRound };
}

export function RoleGroupBadge({ groupName }: { groupName: string }) {
  const t = useTranslations("backoffice.common");

  const role = resolveSystemRole(groupName);
  if (role) {
    const visual = resolveRoleVisual(role);
    return (
      <BackofficeStatusChip tone={visual.tone} icon={visual.icon}>
        {t(`rbac.roles.values.${role}`)}
      </BackofficeStatusChip>
    );
  }

  return (
    <BackofficeStatusChip tone="info" icon={UsersRound}>
      {groupName || "-"}
    </BackofficeStatusChip>
  );
}
