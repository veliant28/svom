import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export type BackofficeStatusChipTone =
  | "success"
  | "warning"
  | "error"
  | "info"
  | "orange"
  | "gray"
  | "black"
  | "red"
  | "blue";
export type BackofficeStatusChipPalette = "default" | "countdown";

export const BACKOFFICE_STATUS_CHIP_BASE_CLASS =
  "inline-flex w-fit items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-semibold";

const BACKOFFICE_STATUS_CHIP_TONE_CLASSES: Record<BackofficeStatusChipTone, string> = {
  success: "border-emerald-700/45 bg-emerald-700/16 text-emerald-900 dark:border-emerald-300/70 dark:bg-emerald-500/24 dark:text-emerald-50",
  warning: "border-amber-700/45 bg-amber-700/18 text-amber-900 dark:border-amber-300/70 dark:bg-amber-500/24 dark:text-amber-50",
  error: "border-red-700/45 bg-red-700/16 text-red-900 dark:border-red-300/70 dark:bg-red-500/24 dark:text-red-50",
  info: "border-slate-700/45 bg-slate-700/16 text-slate-900 dark:border-slate-300/70 dark:bg-slate-500/22 dark:text-slate-50",
  orange: "border-orange-700/45 bg-orange-700/16 text-orange-900 dark:border-orange-300/70 dark:bg-orange-500/24 dark:text-orange-50",
  gray: "border-zinc-700/45 bg-zinc-700/16 text-zinc-900 dark:border-zinc-300/70 dark:bg-zinc-500/22 dark:text-zinc-50",
  black: "border-neutral-900/70 bg-neutral-900/20 text-neutral-950 dark:border-neutral-100/70 dark:bg-neutral-100/12 dark:text-neutral-50",
  red: "border-red-700/45 bg-red-700/16 text-red-900 dark:border-red-300/70 dark:bg-red-500/24 dark:text-red-50",
  blue: "border-blue-700/45 bg-blue-700/16 text-blue-900 dark:border-blue-300/70 dark:bg-blue-500/24 dark:text-blue-50",
};

const BACKOFFICE_STATUS_CHIP_COUNTDOWN_CLASSES: Record<BackofficeStatusChipTone, string> = {
  success: "border-blue-700/45 bg-blue-700/16 text-blue-900 dark:border-blue-300/70 dark:bg-blue-500/24 dark:text-blue-50",
  warning: BACKOFFICE_STATUS_CHIP_TONE_CLASSES.warning,
  error: BACKOFFICE_STATUS_CHIP_TONE_CLASSES.error,
  info: BACKOFFICE_STATUS_CHIP_TONE_CLASSES.info,
  orange: BACKOFFICE_STATUS_CHIP_TONE_CLASSES.orange,
  gray: BACKOFFICE_STATUS_CHIP_TONE_CLASSES.gray,
  black: BACKOFFICE_STATUS_CHIP_TONE_CLASSES.black,
  red: BACKOFFICE_STATUS_CHIP_TONE_CLASSES.red,
  blue: BACKOFFICE_STATUS_CHIP_TONE_CLASSES.blue,
};

function resolveToneClass(tone: BackofficeStatusChipTone, palette: BackofficeStatusChipPalette): string {
  if (palette === "countdown") {
    return BACKOFFICE_STATUS_CHIP_COUNTDOWN_CLASSES[tone];
  }
  return BACKOFFICE_STATUS_CHIP_TONE_CLASSES[tone];
}

interface BackofficeStatusChipProps {
  tone: BackofficeStatusChipTone;
  children: ReactNode;
  icon?: LucideIcon;
  palette?: BackofficeStatusChipPalette;
  className?: string;
}

export function BackofficeStatusChip({
  tone,
  children,
  icon: Icon,
  palette = "default",
  className = "",
}: BackofficeStatusChipProps) {
  return (
    <span className={`${BACKOFFICE_STATUS_CHIP_BASE_CLASS} ${resolveToneClass(tone, palette)} ${className}`.trim()}>
      {Icon ? <Icon className="size-3.5 shrink-0" /> : null}
      <span>{children}</span>
    </span>
  );
}
