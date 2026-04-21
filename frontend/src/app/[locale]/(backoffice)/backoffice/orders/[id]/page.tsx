import { OrderDetailPage } from "@/features/backoffice/pages/order-detail-page";
import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function OrderDetailRoute({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const resolved = await params;
  await ensureBackofficeRouteCapability(resolved.locale, BACKOFFICE_CAPABILITIES.ordersView);
  return <OrderDetailPage orderId={resolved.id} />;
}
