import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { LoyaltyPage } from "@/features/backoffice/pages/loyalty-page";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function BackofficeLoyaltyRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.loyaltyIssue);
  return <LoyaltyPage />;
}
