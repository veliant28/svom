import { AutoDbMatchingPage } from "@/features/backoffice/pages/autodb-matching-page";
import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function BackofficeAutoDbMatchingRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.autocatalogView);
  return <AutoDbMatchingPage />;
}
