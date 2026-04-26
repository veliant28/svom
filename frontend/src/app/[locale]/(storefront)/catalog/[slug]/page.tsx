import { ProductDetailPage } from "@/features/catalog/pages/product-detail-page";
import type { Metadata } from "next";

import type { ProductDetail } from "@/features/catalog/types";
import { getSeoPublicConfig } from "@/features/seo/server/get-seo-public-config";
import { resolveSeoMetadata } from "@/features/seo/server/resolve-seo-metadata";
import { siteConfig } from "@/shared/config/site";

export default async function CatalogProductDetailRoute({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <ProductDetailPage slug={slug} />;
}

async function getProductDetailForMetadata(slug: string, locale: string): Promise<ProductDetail | null> {
  try {
    const response = await fetch(`${siteConfig.serverApiBaseUrl}/catalog/products/${slug}/?locale=${encodeURIComponent(locale)}`, {
      method: "GET",
      cache: "no-store",
      credentials: "omit",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as ProductDetail;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}): Promise<Metadata> {
  const { locale, slug } = await params;
  const product = await getProductDetailForMetadata(slug, locale);
  const seoConfig = await getSeoPublicConfig();

  return resolveSeoMetadata({
    config: seoConfig,
    path: `/catalog/${slug}`,
    locale,
    entityType: "product",
    context: {
      name: product?.name || slug,
      brand: product?.brand?.name || "",
      category: product?.category?.name || "",
      article: product?.article || "",
      price: product?.final_price || "",
      site_name: "SVOM",
    },
    fallbackTitle: product?.name || "SVOM",
    fallbackDescription: product?.short_description || "",
  });
}
