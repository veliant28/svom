import { redirect } from "next/navigation";

type ImportErrorsRouteProps = {
  params: Promise<{
    locale: string;
  }>;
  searchParams?: Promise<{
    supplier?: string | string[];
  }>;
};

export default async function ImportErrorsRoute({ params, searchParams }: ImportErrorsRouteProps) {
  const { locale } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const supplierRaw = resolvedSearchParams?.supplier;
  const supplier = Array.isArray(supplierRaw) ? supplierRaw[0] : supplierRaw;
  const supplierQuery = supplier ? `?supplier=${encodeURIComponent(supplier)}` : "";
  redirect(`/${locale}/backoffice/suppliers/import-errors${supplierQuery}`);
}
