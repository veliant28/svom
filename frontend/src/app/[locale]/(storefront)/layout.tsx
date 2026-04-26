import type { ReactNode } from "react";

import { getCategories } from "@/features/catalog/api/get-categories";
import { Footer } from "@/shared/components/layout/footer";
import { Header } from "@/shared/components/layout/header";
import type { CategorySummary } from "@/features/catalog/types";

async function getHeaderCategories(locale: string): Promise<CategorySummary[]> {
  try {
    return await getCategories(locale);
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
  const headerCategories = await getHeaderCategories(locale);

  return (
    <div className="flex min-h-screen flex-col">
      <Header initialCategories={headerCategories} />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
