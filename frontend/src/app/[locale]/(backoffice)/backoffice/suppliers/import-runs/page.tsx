import { SupplierImportRunsPage } from "@/features/backoffice/pages/supplier-import-runs-page";
import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function BackofficeSuppliersImportRunsRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.importsView);
  return <SupplierImportRunsPage />;
}
