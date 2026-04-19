import { redirect } from "next/navigation";

export default async function SearchRoutePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  redirect(`/${locale}/catalog`);
}
