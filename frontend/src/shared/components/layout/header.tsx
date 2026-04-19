"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { HeaderParentCategoryButtons } from "@/shared/components/layout/header/categories/header-parent-category-buttons";
import { StorefrontNav } from "@/shared/components/layout/header/storefront-nav";
import { HeaderUserMenu } from "@/shared/components/layout/header/user-menu";
import { LocaleSwitcher } from "@/shared/components/layout/locale-switcher";
import { ThemeToggle } from "@/shared/components/layout/theme-toggle";

export function Header() {
  const t = useTranslations("common.header");
  const brand = t("brand");
  const brandTooltipTitle = t("brandTooltip.title");
  const brandTooltipSlogan = t("brandTooltip.slogan");
  const [isBrandTooltipVisible, setIsBrandTooltipVisible] = useState(false);
  const tooltipHideTimerRef = useRef<number | null>(null);
  const vIndex = brand.indexOf("V");
  const brandPrefix = vIndex >= 0 ? brand.slice(0, vIndex) : brand;
  const brandSuffix = vIndex >= 0 ? brand.slice(vIndex + 1) : "";

  const clearTooltipTimer = () => {
    if (tooltipHideTimerRef.current !== null) {
      window.clearTimeout(tooltipHideTimerRef.current);
      tooltipHideTimerRef.current = null;
    }
  };

  const scheduleTooltipHide = (delayMs = 1800) => {
    clearTooltipTimer();
    tooltipHideTimerRef.current = window.setTimeout(() => {
      setIsBrandTooltipVisible(false);
      tooltipHideTimerRef.current = null;
    }, delayMs);
  };

  const hideTooltip = () => {
    clearTooltipTimer();
    setIsBrandTooltipVisible(false);
  };

  useEffect(() => {
    return () => {
      clearTooltipTimer();
    };
  }, []);

  return (
    <header
      className="sticky top-0 z-30 border-b backdrop-blur"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "color-mix(in srgb, var(--surface) 90%, transparent)",
      }}
    >
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
        <div className="flex min-w-0 flex-1 items-center gap-6">
          <span
            className="relative inline-flex"
            onMouseEnter={() => {
              clearTooltipTimer();
              setIsBrandTooltipVisible(true);
            }}
            onMouseLeave={hideTooltip}
            onFocusCapture={() => {
              setIsBrandTooltipVisible(true);
              scheduleTooltipHide();
            }}
            onBlurCapture={(event) => {
              const nextTarget = event.relatedTarget as Node | null;
              if (!event.currentTarget.contains(nextTarget)) {
                hideTooltip();
              }
            }}
            onTouchStart={() => {
              setIsBrandTooltipVisible(true);
              scheduleTooltipHide();
            }}
          >
            <Link
              href="/"
              aria-label={`${brandTooltipTitle}. ${brandTooltipSlogan}`}
              className="inline-flex h-10 shrink-0 items-center gap-1 rounded-lg px-1 text-[2.5rem] font-semibold leading-none"
            >
              {vIndex >= 0 ? (
                <>
                  <span>{brandPrefix}</span>
                  <Image
                    src="/icons/logo-v.svg"
                    alt="V"
                    width={64}
                    height={64}
                    className="inline-block h-[64px] w-[64px] align-[-0.06em]"
                    priority
                  />
                  <span>{brandSuffix}</span>
                </>
              ) : (
                <span>{brand}</span>
              )}
            </Link>
            <span role="tooltip" className={`header-brand-tooltip ${isBrandTooltipVisible ? "block" : "hidden"}`}>
              <strong className="header-brand-tooltip-title">{brandTooltipTitle}</strong>
              <span className="header-brand-tooltip-slogan">{brandTooltipSlogan}</span>
            </span>
          </span>
          <HeaderParentCategoryButtons />
        </div>

        <div className="flex items-center gap-2">
          <StorefrontNav showCategories={false} />
          <HeaderUserMenu />
          <LocaleSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
