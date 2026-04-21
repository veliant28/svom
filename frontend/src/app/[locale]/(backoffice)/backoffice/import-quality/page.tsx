import { redirect } from "next/navigation";

import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

type ImportQualityRouteProps = {
  params: Promise<{
    locale: string;
  }>;
  searchParams?: Promise<{
    supplier?: string | string[];
  }>;
};

export default async function ImportQualityRoute({ params, searchParams }: ImportQualityRouteProps) {
  const { locale } = await params;
  await ensureBackofficeRouteCapability(locale, BACKOFFICE_CAPABILITIES.importsView);
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const supplierRaw = resolvedSearchParams?.supplier;
  const supplier = Array.isArray(supplierRaw) ? supplierRaw[0] : supplierRaw;
  const supplierQuery = supplier ? `?supplier=${encodeURIComponent(supplier)}` : "";
  redirect(`/${locale}/backoffice/suppliers/import-quality${supplierQuery}`);
}
