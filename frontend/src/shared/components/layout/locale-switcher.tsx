"use client";

import { Globe } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { usePathname, useRouter } from "@/i18n/navigation";
import type { AppLocale } from "@/i18n/routing";

const localeOptions: AppLocale[] = ["uk", "ru", "en"];

export function LocaleSwitcher() {
  const t = useTranslations("common.header");
  const locale = useLocale() as AppLocale;
  const router = useRouter();
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

  return (
    <div ref={wrapperRef} className="relative inline-flex">
      <span className="group relative inline-flex">
        <button
          type="button"
          className="header-control"
          aria-label={t("tooltips.language")}
          aria-haspopup="menu"
          aria-expanded={isOpen ? "true" : "false"}
          onClick={() => setIsOpen((previous) => !previous)}
        >
          <Globe size={18} />
        </button>
        <span role="tooltip" className="header-tooltip hidden group-hover:block">
          {t("tooltips.language")}
        </span>
      </span>

      {isOpen ? (
        <div className="header-dropdown min-w-[10rem]" role="menu" aria-label={t("tooltips.language")}>
          {localeOptions.map((item) => (
            <button
              key={item}
              type="button"
              className="header-menu-item justify-between"
              role="menuitemradio"
              aria-checked={locale === item}
              onClick={() => {
                router.replace(pathname, { locale: item });
                setIsOpen(false);
              }}
            >
              <span>{t(`languages.${item}`)}</span>
              <span
                className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                style={{
                  backgroundColor: locale === item ? "color-mix(in srgb, var(--accent) 24%, transparent)" : "transparent",
                  color: "var(--text)",
                }}
              >
                {item.toUpperCase()}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
