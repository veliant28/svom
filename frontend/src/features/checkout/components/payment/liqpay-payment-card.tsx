"use client";

import { useTheme } from "@/shared/components/theme/theme-provider";

export function LiqpayPaymentCard({
  title,
  selected,
  onSelect,
}: {
  title: string;
  hint: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const { theme } = useTheme();
  const backgroundColor = theme === "dark" ? "#D8D8D8" : "#A5A5A5";
  const logoPath = theme === "dark" ? "/icons/liqpay.svg" : "/icons/logo_liqpay_for-black.svg";

  return (
    <div>
      <button
        type="button"
        className="relative inline-flex h-11 w-full items-center justify-center overflow-hidden rounded-md border transition"
        style={{
          borderColor: selected ? "var(--accent)" : "var(--border)",
          backgroundColor,
          boxShadow: selected ? "0 0 0 2px var(--accent)" : "none",
        }}
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={title}
      >
        <span
          aria-hidden
          className="absolute inset-0 flex items-center justify-center"
        >
          <span
            className="block h-[14px] w-[67px]"
            style={{
              backgroundImage: `url('${logoPath}')`,
              backgroundRepeat: "no-repeat",
              backgroundPosition: "center",
              backgroundSize: "contain",
            }}
          />
        </span>
      </button>
    </div>
  );
}
