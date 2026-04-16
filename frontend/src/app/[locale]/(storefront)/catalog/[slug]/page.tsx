import { ProductDetailPage } from "@/features/catalog/pages/product-detail-page";

export default async function CatalogProductDetailRoute({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <ProductDetailPage slug={slug} />;
}
