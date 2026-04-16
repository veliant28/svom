"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";

import { useTheme } from "@/shared/components/theme/theme-provider";

export function ThemeToggle() {
  const t = useTranslations("common.theme");
  const { theme, themeMode, toggleTheme } = useTheme();

  const modeLabel = t(`mode.${themeMode}`);
  const title = `${t("switch")}: ${modeLabel}`;

  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={title}
        className="inline-flex h-10 w-10 items-center justify-center rounded-lg border"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        {themeMode === "system" ? <Monitor size={18} /> : theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-30 mt-2 hidden -translate-x-1/2 whitespace-nowrap rounded-md border px-2 py-1 text-xs shadow-md group-hover:block group-focus-within:block"
        style={{
          borderColor: "color-mix(in srgb, var(--border) 82%, #0f172a 18%)",
          backgroundColor: "var(--surface)",
          color: "var(--text)",
        }}
      >
        {title}
      </span>
    </span>
  );
}
