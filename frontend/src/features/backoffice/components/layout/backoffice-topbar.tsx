"use client";

import { Menu, Monitor, Moon, Sun } from "lucide-react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useBackofficeHeaderConfig } from "@/features/backoffice/components/layout/backoffice-header-context";
import type { BackofficeUser } from "@/features/backoffice/types/backoffice";
import { LocaleSwitcher } from "@/shared/components/layout/locale-switcher";
import { useTheme } from "@/shared/components/theme/theme-provider";

export function BackofficeTopbar({ onToggleSidebar, user }: { onToggleSidebar: () => void; user: BackofficeUser }) {
  const t = useTranslations("backoffice.common");
  const locale = useLocale();
  const router = useRouter();
  const { theme, themeMode, toggleTheme } = useTheme();
  const { logout } = useAuth();
  const config = useBackofficeHeaderConfig();

  const displayName = user.username || user.email;
  const title = config.title || displayName;
  const themeTooltip = `${t("topbar.toggleTheme")}: ${t(`topbar.themeMode.${themeMode}`)}`;

  return (
    <header className="sticky top-0 z-20 border-b px-4 py-3 backdrop-blur" style={{ borderColor: "var(--border)", backgroundColor: "color-mix(in oklab, var(--surface) 88%, transparent)" }}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border lg:hidden"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={onToggleSidebar}
            aria-label={t("topbar.toggleSidebar")}
          >
            <Menu size={18} />
          </button>
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-[0.16em]" style={{ color: "var(--muted)" }}>
              {t("topbar.role")}
            </p>
            <p className="mt-0.5 min-w-0 truncate text-sm font-semibold lg:text-base">{title}</p>
          </div>
          {config.switcher ? <div className="flex flex-wrap items-center gap-2">{config.switcher}</div> : null}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          {config.actions ? <div className="flex flex-wrap items-center gap-2">{config.actions}</div> : null}
          {config.actionsBeforeLogout ? <div className="flex flex-wrap items-center gap-2">{config.actionsBeforeLogout}</div> : null}
          <p className="hidden text-xs lg:block" style={{ color: "var(--muted)" }}>
            {displayName}
          </p>
          <div className="backoffice-topbar-locale-switcher">
            <LocaleSwitcher />
          </div>
          <span className="group relative inline-flex">
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={toggleTheme}
              aria-label={themeTooltip}
            >
              {themeMode === "system" ? <Monitor size={16} /> : theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
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
              {themeTooltip}
            </span>
          </span>
          <button
            type="button"
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void logout().then(() => {
                router.push(`/${locale}/login`);
              });
            }}
          >
            {t("topbar.logout")}
          </button>
        </div>
      </div>
    </header>
  );
}
