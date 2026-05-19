import { AccountReturnsPage } from "@/features/account/pages/account-returns-page";
import { requireReturnsEnabled } from "@/features/account/server/require-returns-enabled";

export default async function AccountReturnsRoutePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  await requireReturnsEnabled(locale, `/${locale}/account/returns`);
  return <AccountReturnsPage />;
}
