import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { routing } from "@/i18n/routing";
import { GoogleTrackingScripts } from "@/features/seo/components/google-tracking-scripts";
import { getSeoPublicConfig } from "@/features/seo/server/get-seo-public-config";
import { resolveSeoMetadata } from "@/features/seo/server/resolve-seo-metadata";
import { StorefrontProviders } from "@/shared/components/providers/storefront-providers";
import { ThemeProvider } from "@/shared/components/theme/theme-provider";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;

  if (!hasLocale(routing.locales, locale)) {
    return {};
  }

  const t = await getTranslations({ locale, namespace: "common.meta" });
  const seoConfig = await getSeoPublicConfig();
  const resolved = resolveSeoMetadata({
    config: seoConfig,
    path: "/",
    locale,
    entityType: "page",
    context: {
      name: t("title"),
      site_name: "SVOM",
    },
    fallbackTitle: t("title"),
    fallbackDescription: t("description"),
  });

  const verificationToken = String(
    seoConfig?.google?.search_console_verification_token
    || seoConfig?.google?.google_site_verification_meta
    || "",
  ).trim();

  return {
    ...resolved,
    verification: verificationToken ? { google: verificationToken } : undefined,
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  setRequestLocale(locale);
  const messages = await getMessages();
  const seoConfig = await getSeoPublicConfig();

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <ThemeProvider>
        <StorefrontProviders>{children}</StorefrontProviders>
        <GoogleTrackingScripts settings={seoConfig?.google} />
      </ThemeProvider>
    </NextIntlClientProvider>
  );
}
