import type { ReactNode } from "react";

import { getHeaderNavigation as fetchHeaderNavigation } from "@/features/catalog/api/get-categories";
import { Footer } from "@/shared/components/layout/footer";
import { Header } from "@/shared/components/layout/header";
import type { HeaderCategoryParent } from "@/shared/components/layout/header/categories/header-category.types";

async function loadHeaderNavigation(locale: string): Promise<HeaderCategoryParent[]> {
  try {
    return await fetchHeaderNavigation(locale);
  } catch {
    return [];
  }
}

export default async function StorefrontLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const headerNavigation = await loadHeaderNavigation(locale);

  return (
    <div className="flex min-h-screen flex-col">
      <Header initialNavigation={headerNavigation} />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
