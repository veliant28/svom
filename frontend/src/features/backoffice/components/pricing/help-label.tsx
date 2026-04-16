"use client";

import { CircleHelp } from "lucide-react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";

type HelpLabelProps = {
  label: string;
  tooltip: string;
};

export function HelpLabel({ label, tooltip }: HelpLabelProps) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <span className="text-sm font-semibold">{label}</span>
      <BackofficeTooltip content={tooltip} align="start" placement="top">
        <button
          type="button"
          className="inline-flex h-5 w-5 items-center justify-center rounded-full border"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          aria-label={tooltip}
        >
          <CircleHelp className="h-3.5 w-3.5" />
        </button>
      </BackofficeTooltip>
    </div>
  );
}
