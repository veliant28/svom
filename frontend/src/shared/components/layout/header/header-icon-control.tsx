"use client";

import type { CSSProperties, ReactNode } from "react";

import { Link } from "@/i18n/navigation";

type ControlBaseProps = {
  tooltip: string;
  ariaLabel?: string;
  icon: ReactNode;
  isActive?: boolean;
  badge?: number;
  badgeTone?: "accent" | "indigo";
  className?: string;
  style?: CSSProperties;
};

type HeaderIconLinkProps = ControlBaseProps & {
  href: string;
};

type HeaderIconButtonProps = ControlBaseProps & {
  onClick: () => void | Promise<void>;
  disabled?: boolean;
};

function HeaderControlTooltip({ label }: { label: string }) {
  return (
    <span role="tooltip" className="header-tooltip hidden group-hover:block group-focus-within:block">
      {label}
    </span>
  );
}

function HeaderControlBadge({ value, tone = "accent" }: { value: number; tone?: "accent" | "indigo" }) {
  if (value <= 0) {
    return null;
  }

  const palette =
    tone === "indigo"
      ? { backgroundColor: "#3340a8", color: "#ffffff" }
      : { backgroundColor: "var(--accent)", color: "#ffffff" };

  return (
    <span
      className="absolute -right-1.5 -top-1.5 inline-flex min-w-[1.1rem] items-center justify-center rounded-full px-1 text-[10px] font-semibold leading-4"
      style={palette}
    >
      {value > 99 ? "99+" : value}
    </span>
  );
}

export function HeaderIconLink({
  href,
  tooltip,
  ariaLabel,
  icon,
  isActive = false,
  badge = 0,
  badgeTone = "accent",
  className = "",
  style,
}: HeaderIconLinkProps) {
  return (
    <span className="group relative inline-flex">
      <Link
        href={href}
        aria-label={ariaLabel ?? tooltip}
        className={`header-control relative ${className}`.trim()}
        data-active={isActive ? "true" : "false"}
        style={style}
      >
        {icon}
        <HeaderControlBadge value={badge} tone={badgeTone} />
      </Link>
      <HeaderControlTooltip label={tooltip} />
    </span>
  );
}

export function HeaderIconButton({
  tooltip,
  ariaLabel,
  icon,
  onClick,
  isActive = false,
  badge = 0,
  badgeTone = "accent",
  className = "",
  disabled = false,
  style,
}: HeaderIconButtonProps) {
  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label={ariaLabel ?? tooltip}
        onClick={() => {
          void onClick();
        }}
        className={`header-control relative ${className}`.trim()}
        data-active={isActive ? "true" : "false"}
        disabled={disabled}
        style={style}
      >
        {icon}
        <HeaderControlBadge value={badge} tone={badgeTone} />
      </button>
      <HeaderControlTooltip label={tooltip} />
    </span>
  );
}
