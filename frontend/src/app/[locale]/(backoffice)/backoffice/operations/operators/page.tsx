import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { BackofficeStaffStatsPage } from "@/features/backoffice/pages/backoffice-staff-stats-page";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function BackofficeOperatorsStatsRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.backofficeAccess);
  return <BackofficeStaffStatsPage role="operator" />;
}

