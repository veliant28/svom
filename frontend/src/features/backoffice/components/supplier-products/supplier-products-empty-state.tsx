type Translator = (key: string, values?: Record<string, string | number>) => string;

export function supplierProductsEmptyLabel(t: Translator): string {
  return t("productsPage.empty");
}
