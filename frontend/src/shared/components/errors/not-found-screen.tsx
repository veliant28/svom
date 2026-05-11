"use client";

import { useMemo } from "react";
import { usePathname } from "next/navigation";

const LOCALES = new Set(["uk", "ru", "en"]);

type Copy = {
  title: string;
  subtitle: string;
  action: string;
};

const COPY: Record<string, Copy> = {
  uk: {
    title: "Сторінку не знайдено",
    subtitle: "Адреса змінилась або сторінка більше не доступна.",
    action: "На головну",
  },
  ru: {
    title: "Страница не найдена",
    subtitle: "Адрес изменился или страница больше не доступна.",
    action: "На главную",
  },
  en: {
    title: "Page not found",
    subtitle: "The address changed or this page is no longer available.",
    action: "Home",
  },
};

function resolveLocale(pathname: string | null | undefined): string {
  const firstSegment = (pathname ?? "/").split("/").filter(Boolean)[0];
  return firstSegment && LOCALES.has(firstSegment) ? firstSegment : "uk";
}

export function NotFoundScreen() {
  const pathname = usePathname();
  const locale = useMemo(() => resolveLocale(pathname), [pathname]);
  const copy = COPY[locale] ?? COPY.uk;
  const homeHref = locale === "uk" ? "/uk" : `/${locale}`;

  return (
    <section className="error404-screen" role="alert" aria-live="polite">
      <div className="error404-content">
        <p className="error404-brand">SVOM</p>
        <div className="error404-number" aria-hidden="true">
          <span className="error404-number-text">404</span>
        </div>
        <h1 className="error404-title">{copy.title}</h1>
        <p className="error404-subtitle">{copy.subtitle}</p>
        <a className="error404-action" href={homeHref}>
          {copy.action}
        </a>
      </div>
    </section>
  );
}
