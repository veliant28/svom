"use client";

import { CarFront, Heart, LogIn, LogOut, PackageSearch, Shield, UserRound } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { Link, usePathname } from "@/i18n/navigation";
import { HeaderIconLink } from "@/shared/components/layout/header/header-icon-control";

function getUserInitials(input: { lastName?: string; username?: string; email?: string }): string {
  const first = (input.username?.trim() || input.email?.trim() || "")[0] ?? "";
  const last = (input.lastName?.trim() || "")[0] ?? "";
  const full = `${first}${last}`.toUpperCase();
  if (full) {
    return full;
  }

  const fallback = input.username?.trim() || input.email?.trim() || "U";
  return fallback[0]?.toUpperCase() ?? "U";
}

function isActivePath(pathname: string, target: string): boolean {
  return pathname === target || pathname.startsWith(`${target}/`);
}

export function HeaderUserMenu() {
  const t = useTranslations("common.header");
  const { user, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  const initials = useMemo(
    () =>
      getUserInitials({
        lastName: user?.last_name,
        username: user?.username,
        email: user?.email,
      }),
    [user?.email, user?.last_name, user?.username],
  );

  if (!isAuthenticated) {
    return <HeaderIconLink href="/login" tooltip={t("tooltips.login")} icon={<LogIn size={18} />} isActive={isActivePath(pathname, "/login")} />;
  }

  const isAdmin = Boolean(user?.is_staff || user?.is_superuser);

  return (
    <div ref={wrapperRef} className="relative inline-flex">
      <span className="group relative inline-flex">
        <button
          type="button"
          className="header-control"
          aria-haspopup="menu"
          aria-expanded={isOpen ? "true" : "false"}
          aria-label={t("tooltips.account")}
          onClick={() => setIsOpen((previous) => !previous)}
        >
          <span
            className="inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold"
            style={{
              backgroundColor: "color-mix(in srgb, var(--accent) 18%, var(--surface))",
              color: "var(--text)",
            }}
          >
            {initials}
          </span>
        </button>
        <span role="tooltip" className="header-tooltip hidden group-hover:block">
          {t("tooltips.account")}
        </span>
      </span>

      {isOpen ? (
        <div className="header-dropdown" role="menu" aria-label={t("tooltips.account")}>
          {isAdmin ? (
            <>
              <Link
                href="/backoffice"
                className="header-menu-item"
                role="menuitem"
                onClick={() => setIsOpen(false)}
              >
                <Shield size={15} />
                <span>{t("menu.backoffice")}</span>
              </Link>
              <div className="header-dropdown-divider" />
            </>
          ) : null}

          <Link
            href="/account/profile"
            className="header-menu-item"
            role="menuitem"
            onClick={() => setIsOpen(false)}
          >
            <UserRound size={15} />
            <span>{t("menu.profile")}</span>
          </Link>

          <Link
            href="/account/orders"
            className="header-menu-item"
            role="menuitem"
            onClick={() => setIsOpen(false)}
          >
            <PackageSearch size={15} />
            <span>{t("menu.orders")}</span>
          </Link>

          <Link
            href="/wishlist"
            className="header-menu-item"
            role="menuitem"
            onClick={() => setIsOpen(false)}
          >
            <Heart size={15} />
            <span>{t("menu.favorites")}</span>
          </Link>

          <Link
            href="/garage"
            className="header-menu-item"
            role="menuitem"
            onClick={() => setIsOpen(false)}
          >
            <CarFront size={15} />
            <span>{t("menu.garage")}</span>
          </Link>

          <div className="header-dropdown-divider" />
          <button
            type="button"
            className="header-menu-item header-menu-item-danger"
            role="menuitem"
            onClick={() => {
              setIsOpen(false);
              void logout();
            }}
          >
            <LogOut size={15} />
            <span>{t("menu.logout")}</span>
          </button>
        </div>
      ) : null}
    </div>
  );
}
