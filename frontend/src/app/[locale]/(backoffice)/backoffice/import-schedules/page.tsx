import { redirect } from "next/navigation";

type ImportSchedulesRouteProps = {
  params: Promise<{
    locale: string;
  }>;
  searchParams?: Promise<{
    supplier?: string | string[];
  }>;
};

export default async function ImportSchedulesRoute({ params, searchParams }: ImportSchedulesRouteProps) {
  const { locale } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const supplierRaw = resolvedSearchParams?.supplier;
  const supplier = Array.isArray(supplierRaw) ? supplierRaw[0] : supplierRaw;
  const supplierQuery = supplier ? `?supplier=${encodeURIComponent(supplier)}` : "";
  redirect(`/${locale}/backoffice/suppliers${supplierQuery}`);
}
