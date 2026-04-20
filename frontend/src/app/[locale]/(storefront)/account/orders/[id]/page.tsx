import { AccountOrderDetailPage } from "@/features/account/pages/account-order-detail-page";

export default async function AccountOrderDetailRoutePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AccountOrderDetailPage orderId={id} />;
}
