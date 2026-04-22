import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { SupportWallboardPage } from "@/features/backoffice/pages/support-wallboard-page";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function BackofficeSupportWallboardRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.customersSupport);
  return <SupportWallboardPage />;
}
