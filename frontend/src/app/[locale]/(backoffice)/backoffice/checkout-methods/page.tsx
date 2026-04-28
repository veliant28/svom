import { CheckoutMethodsPage } from "@/features/backoffice/pages/checkout-methods-page";
import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function CheckoutMethodsRoute({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, BACKOFFICE_CAPABILITIES.checkoutMethodsManage);
  return <CheckoutMethodsPage />;
}
