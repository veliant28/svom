"use client";

import { CarFront, Heart, LogIn, LogOut, Search, Shield, ShoppingCart } from "lucide-react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useCart } from "@/features/cart/hooks/use-cart";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/shared/components/layout/locale-switcher";
import { ThemeToggle } from "@/shared/components/layout/theme-toggle";

export function Header() {
  const t = useTranslations("common.header");
  const { user, isAuthenticated, logout } = useAuth();
  const { itemsCount } = useCart();

  return (
    <header className="sticky top-0 z-30 border-b backdrop-blur" style={{ borderColor: "var(--border)", backgroundColor: "color-mix(in srgb, var(--surface) 88%, transparent)" }}>
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="inline-flex items-center gap-2 text-lg font-semibold">
          <CarFront size={20} />
          <span>{t("brand")}</span>
        </Link>

        <nav className="hidden items-center gap-4 text-sm md:flex">
          <Link href="/catalog">{t("catalog")}</Link>
          <Link href="/garage">{t("garage")}</Link>
          <Link href="/wishlist" className="inline-flex items-center gap-1">
            <Heart size={14} />
            {t("wishlist")}
          </Link>
          <Link href="/cart" className="inline-flex items-center gap-1">
            <ShoppingCart size={14} />
            {t("cart", { count: itemsCount })}
          </Link>
          <Link href="/search" className="inline-flex items-center gap-1">
            <Search size={14} />
            {t("search")}
          </Link>
          {user?.is_staff || user?.is_superuser ? (
            <Link href="/backoffice" className="inline-flex items-center gap-1">
              <Shield size={14} />
              {t("backoffice")}
            </Link>
          ) : null}
        </nav>

        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <>
              <span className="hidden text-xs md:inline" style={{ color: "var(--muted)" }}>
                {user?.email}
              </span>
              <button
                type="button"
                className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                onClick={() => void logout()}
              >
                <LogOut size={13} />
                {t("logout")}
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <LogIn size={13} />
              {t("login")}
            </Link>
          )}
          <LocaleSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
