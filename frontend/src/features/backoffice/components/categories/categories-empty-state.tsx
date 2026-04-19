type Translator = (key: string, values?: Record<string, string | number>) => string;

export function categoriesEmptyLabel(t: Translator): string {
  return t("categories.states.empty");
}
