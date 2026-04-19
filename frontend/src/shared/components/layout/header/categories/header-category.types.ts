import type { CategorySummary } from "@/features/catalog/types";

export type HeaderCategorySection = {
  id: string;
  title: string | null;
  items: CategorySummary[];
};

export type HeaderCategoryParent = {
  id: string;
  name: string;
  slug: string;
  sections: HeaderCategorySection[];
};
