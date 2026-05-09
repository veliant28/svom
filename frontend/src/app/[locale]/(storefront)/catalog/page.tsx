import { CatalogPage } from "@/features/catalog/pages/catalog-page";
import { getTranslations } from "next-intl/server";
import type { Metadata } from "next";

import { getCategories } from "@/features/catalog/api/get-categories";
import type { CategorySummary } from "@/features/catalog/types";
import { getSeoPublicConfig } from "@/features/seo/server/get-seo-public-config";
import { resolveSeoMetadata } from "@/features/seo/server/resolve-seo-metadata";

export default async function CatalogRoutePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  let initialCategories: CategorySummary[] = [];

  try {
    initialCategories = await getCategories(locale);
  } catch {
    initialCategories = [];
  }

  return <CatalogPage initialCategories={initialCategories} />;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "catalog" });
  const seoConfig = await getSeoPublicConfig();

  return resolveSeoMetadata({
    config: seoConfig,
    path: "/catalog",
    locale,
    entityType: "page",
    context: {
      name: t("title"),
      category: t("title"),
      site_name: "SVOM",
    },
    fallbackTitle: t("title"),
    fallbackDescription: t("subtitle"),
  });
}
