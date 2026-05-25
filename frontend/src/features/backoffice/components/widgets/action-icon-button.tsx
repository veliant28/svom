"use client";

import type { LucideIcon } from "lucide-react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";

export function ActionIconButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
  tone = "default",
  dangerFill = false,
  align = "center",
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "danger";
  dangerFill?: boolean;
  align?: "start" | "center" | "end";
}) {
  const isDanger = tone === "danger";
  const isSolidDanger = isDanger && dangerFill;

  return (
    <BackofficeTooltip
      content={label}
      placement="top"
      align={align}
      wrapperClassName="inline-flex"
      tooltipClassName="whitespace-nowrap"
    >
      <button
        type="button"
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
        style={{
          borderColor: isDanger ? "#ef4444" : "var(--border)",
          backgroundColor: isSolidDanger ? "#dc2626" : "var(--surface)",
          color: isSolidDanger ? "#ffffff" : isDanger ? "#dc2626" : "var(--text)",
        }}
        aria-label={label}
        disabled={disabled}
        onClick={onClick}
      >
        <Icon className="h-4 w-4" />
      </button>
    </BackofficeTooltip>
  );
}
