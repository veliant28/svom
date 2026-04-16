"use client";

import type { CSSProperties, ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

type BackofficeTooltipProps = {
  children: ReactNode;
  content: ReactNode;
  placement?: "top" | "bottom";
  align?: "start" | "center" | "end";
  wrapperClassName?: string;
  tooltipClassName?: string;
};

type TooltipPosition = {
  left: number;
  top: number;
};

const VIEWPORT_GAP = 8;
const TOOLTIP_GAP = 8;

export function BackofficeTooltip({
  children,
  content,
  placement = "bottom",
  align = "start",
  wrapperClassName = "",
  tooltipClassName = "",
}: BackofficeTooltipProps) {
  const triggerRef = useRef<HTMLSpanElement | null>(null);
  const tooltipRef = useRef<HTMLSpanElement | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState<TooltipPosition | null>(null);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current || !tooltipRef.current) {
      return;
    }

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const fitsAbove = triggerRect.top - tooltipRect.height - TOOLTIP_GAP >= VIEWPORT_GAP;
    const fitsBelow = triggerRect.bottom + tooltipRect.height + TOOLTIP_GAP <= window.innerHeight - VIEWPORT_GAP;

    let resolvedPlacement = placement;
    if (placement === "bottom" && !fitsBelow && fitsAbove) {
      resolvedPlacement = "top";
    } else if (placement === "top" && !fitsAbove && fitsBelow) {
      resolvedPlacement = "bottom";
    }

    let left = triggerRect.left;
    if (align === "center") {
      left = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2;
    } else if (align === "end") {
      left = triggerRect.right - tooltipRect.width;
    }

    let top = resolvedPlacement === "top"
      ? triggerRect.top - tooltipRect.height - TOOLTIP_GAP
      : triggerRect.bottom + TOOLTIP_GAP;

    left = Math.max(VIEWPORT_GAP, Math.min(left, window.innerWidth - tooltipRect.width - VIEWPORT_GAP));
    top = Math.max(VIEWPORT_GAP, Math.min(top, window.innerHeight - tooltipRect.height - VIEWPORT_GAP));

    setPosition({ left, top });
  }, [align, placement]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    updatePosition();
    const handlePositionUpdate = () => {
      updatePosition();
    };

    window.addEventListener("resize", handlePositionUpdate);
    window.addEventListener("scroll", handlePositionUpdate, true);

    return () => {
      window.removeEventListener("resize", handlePositionUpdate);
      window.removeEventListener("scroll", handlePositionUpdate, true);
    };
  }, [isOpen, updatePosition]);

  return (
    <span
      ref={triggerRef}
      className={wrapperClassName}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onFocusCapture={() => setIsOpen(true)}
      onBlurCapture={() => setIsOpen(false)}
    >
      {children}
      {isOpen ? (
        <span
          ref={tooltipRef}
          role="tooltip"
          className={`pointer-events-none fixed z-[260] rounded-md border px-2 py-1.5 text-xs shadow-md ${tooltipClassName}`}
          style={{
            left: `${position?.left ?? VIEWPORT_GAP}px`,
            top: `${position?.top ?? VIEWPORT_GAP}px`,
            visibility: position ? "visible" : "hidden",
            borderColor: "color-mix(in srgb, var(--border) 82%, #0f172a 18%)",
            backgroundColor: "var(--surface)",
            color: "var(--text)",
          } satisfies CSSProperties}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}
