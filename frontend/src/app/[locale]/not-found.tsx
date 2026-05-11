import { hasLocale } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";

import { routing } from "@/i18n/routing";
import { NotFoundScreen } from "@/shared/components/errors/not-found-screen";

export default async function LocaleNotFound() {
  const requestedLocale = await getLocale();
  const locale = hasLocale(routing.locales, requestedLocale) ? requestedLocale : routing.defaultLocale;
  const t = await getTranslations({ locale, namespace: "common.notFound" });
  const copy = {
    title: t("title"),
    subtitle: t("subtitle"),
    action: t("action"),
  };
  const homeHref = locale === "uk" ? "/uk" : `/${locale}`;

  return <NotFoundScreen copy={copy} homeHref={homeHref} />;
}
