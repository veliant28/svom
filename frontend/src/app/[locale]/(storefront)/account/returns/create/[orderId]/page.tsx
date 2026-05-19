import { AccountReturnsCreateOrderPage } from "@/features/account/pages/account-returns-create-order-page";
import { requireReturnsEnabled } from "@/features/account/server/require-returns-enabled";

export default async function AccountReturnsCreateOrderRoutePage({
  params,
}: {
  params: Promise<{ locale: string; orderId: string }>;
}) {
  const { locale, orderId } = await params;
  await requireReturnsEnabled(locale, `/${locale}/account/returns/create/${orderId}`);
  return <AccountReturnsCreateOrderPage orderId={orderId} />;
}
