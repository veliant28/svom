import { GroupsPage } from "@/features/backoffice/pages/groups-page";
import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function BackofficeGroupsRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.groupsView);
  return <GroupsPage />;
}
