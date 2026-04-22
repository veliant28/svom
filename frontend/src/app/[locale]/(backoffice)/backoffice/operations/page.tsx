import { redirect } from "next/navigation";

export default async function BackofficeOperationsIndexRoute({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  redirect(`/${locale}/backoffice/operations/managers`);
}
