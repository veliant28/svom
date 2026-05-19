import { AccountReturnsCreatePage } from "@/features/account/pages/account-returns-create-page";
import { requireReturnsEnabled } from "@/features/account/server/require-returns-enabled";

export default async function AccountReturnsCreateRoutePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  await requireReturnsEnabled(locale, `/${locale}/account/returns/create`);
  return <AccountReturnsCreatePage />;
}
