import type { ReactNode } from "react";

import { BackofficeShell } from "@/features/backoffice/components/layout/backoffice-shell";
import { requireBackofficeAccess } from "@/features/backoffice/server/require-backoffice-access";

export default async function BackofficeLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const { user } = await requireBackofficeAccess(locale);

  return <BackofficeShell user={user}>{children}</BackofficeShell>;
}
