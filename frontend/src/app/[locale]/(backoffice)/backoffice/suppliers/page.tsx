import { SuppliersPage } from "@/features/backoffice/pages/suppliers-page";
import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function BackofficeSuppliersRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.suppliersView);
  return <SuppliersPage />;
}
