"use client";

import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useFooterSettings } from "@/features/marketing/hooks/use-footer-settings";
import { Link } from "@/i18n/navigation";

export function Footer() {
  const t = useTranslations("common");
  const { user } = useAuth();
  const { settings } = useFooterSettings();
  const canAccessBackoffice = Boolean(user?.has_backoffice_access);
  const workingHoursValue = (settings?.working_hours || "").trim() || t("footer.workingHoursValue");
  const phoneValue = (settings?.phone || "").trim() || t("footer.phoneValue");
  const phoneHref = `tel:${phoneValue.replace(/[^\d+]/g, "")}`;

  return (
    <footer className="footer-hero-surface mt-6 border-t" style={{ borderColor: "var(--border)" }}>
      <div className="mx-auto max-w-6xl px-4 py-4">
        <div
          className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border px-4 py-3 text-sm"
          style={{
            borderColor: "color-mix(in srgb, var(--border) 75%, #0f172a 25%)",
            backgroundColor: "color-mix(in srgb, var(--surface) 78%, transparent)",
            color: "var(--text)",
          }}
        >
          <div className="inline-flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
              {t("footer.navigation")}
            </span>
            <nav className="inline-flex flex-wrap items-center gap-2 font-medium">
              <Link href="/catalog" className="rounded-md px-2 py-1 transition-colors hover:bg-[var(--surface-2)]">
                {t("header.catalog")}
              </Link>
              <Link href="/garage" className="rounded-md px-2 py-1 transition-colors hover:bg-[var(--surface-2)]">
                {t("header.garage")}
              </Link>
              <Link href="/account/support" className="rounded-md px-2 py-1 transition-colors hover:bg-[var(--surface-2)]">
                {t("header.menu.support")}
              </Link>
              {canAccessBackoffice ? (
                <Link href="/backoffice" className="rounded-md px-2 py-1 transition-colors hover:bg-[var(--surface-2)]">
                  {t("header.backoffice")}
                </Link>
              ) : null}
            </nav>
          </div>

          <div className="inline-flex flex-wrap items-center gap-x-4 gap-y-1 text-xs md:ml-auto">
            <span>
              <span className="font-semibold">{t("footer.workingHours")}:</span>{" "}
              <span style={{ color: "var(--muted)" }}>{workingHoursValue}</span>
            </span>
            <a href={phoneHref} className="rounded-md px-2 py-1 font-semibold transition-colors hover:bg-[var(--surface-2)]">
              {t("footer.phone")}: {phoneValue}
            </a>
          </div>
        </div>
        <div
          className="pt-1 text-[11px]"
          style={{
            color: "color-mix(in srgb, #f8fbff 82%, #d8e4ee 18%)",
            textShadow: "0 1px 2px rgba(15,23,42,.35)",
          }}
        >
          © {new Date().getFullYear()} {t("header.brand")}
        </div>
      </div>
    </footer>
  );
}
