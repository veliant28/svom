import { BackofficeDashboardPage } from "@/features/backoffice/pages/backoffice-dashboard-page";
import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function BackofficeHomeRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.backofficeAccess);
  return <BackofficeDashboardPage />;
}
