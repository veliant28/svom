import { NovaPoshtaSendersPage } from "@/features/backoffice/pages/nova-poshta-senders-page";
import { BACKOFFICE_CAPABILITIES } from "@/features/backoffice/lib/capabilities";
import { ensureBackofficeRouteCapability } from "@/features/backoffice/server/ensure-backoffice-route-capability";

export default async function BackofficeNovaPoshtaSendersRoutePage({ params }: { params: Promise<{ locale: string }> }) {
  await ensureBackofficeRouteCapability(params, [BACKOFFICE_CAPABILITIES.ordersManage, BACKOFFICE_CAPABILITIES.customersSupport]);
  return <NovaPoshtaSendersPage />;
}
