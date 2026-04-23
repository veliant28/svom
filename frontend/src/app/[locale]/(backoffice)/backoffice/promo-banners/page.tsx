import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { PromoBannersPage } from "@/features/backoffice/pages/promo-banners-page";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function PromoBannersRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.promoBannersManage);
  return <PromoBannersPage />;
}
