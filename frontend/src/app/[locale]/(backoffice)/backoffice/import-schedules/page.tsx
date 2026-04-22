import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";
import { ImportSchedulesPage } from "@/features/backoffice/pages/import-schedules-page";

export default async function ImportSchedulesRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.schedulesView);
  return <ImportSchedulesPage />;
}
