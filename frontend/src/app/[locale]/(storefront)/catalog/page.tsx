import { CatalogPage } from "@/features/catalog/pages/catalog-page";
import { getTranslations } from "next-intl/server";
import type { Metadata } from "next";

import { getBrands } from "@/features/catalog/api/get-brands";
import { getCategories } from "@/features/catalog/api/get-categories";
import type { BrandSummary, CategorySummary } from "@/features/catalog/types";
import { getSeoPublicConfig } from "@/features/seo/server/get-seo-public-config";
import { resolveSeoMetadata } from "@/features/seo/server/resolve-seo-metadata";

export default async function CatalogRoutePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  let initialBrands: BrandSummary[] = [];
  let initialCategories: CategorySummary[] = [];

  try {
    [initialBrands, initialCategories] = await Promise.all([getBrands(), getCategories(locale)]);
  } catch {
    initialBrands = [];
    initialCategories = [];
  }

  return <CatalogPage initialBrands={initialBrands} initialCategories={initialCategories} />;
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
