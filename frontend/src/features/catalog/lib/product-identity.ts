export function buildProductIdentityParts(params: {
  sku?: string | null;
  brandName?: string | null;
  manufacturerArticle?: string | null;
}): string[] {
  const sku = String(params.sku || "").trim();
  const brand = String(params.brandName || "").trim();
  const manufacturerArticle = String(params.manufacturerArticle || "").trim();

  const parts: string[] = [];
  if (sku) {
    parts.push(sku);
  }
  if (brand && brand !== sku) {
    parts.push(brand);
  }
  if (manufacturerArticle && manufacturerArticle !== sku && manufacturerArticle !== brand) {
    parts.push(manufacturerArticle);
  }
  return parts;
}
