"use client";

import { LoaderCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";

type Translator = (key: string, values?: Record<string, string | number>) => string;
type ToggleItemLike = {
  labelKey: string;
  hintKey: string;
  icon: LucideIcon;
};

export function IntegrationToggleItem({
  item,
  checked,
  isUpdating,
  onToggle,
  t,
}: {
  item: ToggleItemLike;
  checked: boolean;
  isUpdating: boolean;
  onToggle: () => void;
  t: Translator;
}) {
  return (
    <BackofficeTooltip content={t(item.hintKey)} placement="top" align="center" wrapperClassName="block">
      <button
        type="button"
        aria-pressed={checked}
        disabled={isUpdating}
        className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-md border px-2.5 py-2 text-left text-xs disabled:opacity-80"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        onClick={onToggle}
      >
        <span className="inline-flex items-center gap-2">
          <item.icon size={14} />
          <span>{t(item.labelKey)}</span>
        </span>
        <span className="inline-flex items-center gap-2">
          {isUpdating ? <LoaderCircle size={14} className="animate-spin" /> : null}
          <input type="checkbox" checked={checked} readOnly tabIndex={-1} className="pointer-events-none h-4 w-4" />
        </span>
      </button>
    </BackofficeTooltip>
  );
}
