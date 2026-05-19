import { AccountReturnDetailPage } from "@/features/account/pages/account-return-detail-page";
import { requireReturnsEnabled } from "@/features/account/server/require-returns-enabled";

export default async function AccountReturnDetailRoutePage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  await requireReturnsEnabled(locale, `/${locale}/account/returns/${id}`);
  return <AccountReturnDetailPage returnId={id} />;
}
