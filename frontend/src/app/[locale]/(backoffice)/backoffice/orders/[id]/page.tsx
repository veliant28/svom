import { OrderDetailPage } from "@/features/backoffice/pages/order-detail-page";

export default async function OrderDetailRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OrderDetailPage orderId={id} />;
}
