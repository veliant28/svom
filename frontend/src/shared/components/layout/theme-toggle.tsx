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
        className="header-control"
      >
        {themeMode === "system" ? <Monitor size={18} /> : theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
      </button>
      <span
        role="tooltip"
        className="header-tooltip hidden group-hover:block"
      >
        {title}
      </span>
    </span>
  );
}
