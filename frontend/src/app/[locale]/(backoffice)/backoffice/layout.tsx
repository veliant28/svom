import type { ReactNode } from "react";

import { BackofficeShell } from "@/features/backoffice/components/layout/backoffice-shell";
import { requireBackofficeAccess } from "@/features/backoffice/server/require-backoffice-access";
import { logServerTiming } from "@/shared/lib/server-timing";

export default async function BackofficeLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const startedAt = performance.now();
  const { locale } = await params;
  const { user } = await requireBackofficeAccess(locale);

  logServerTiming("backoffice.layout", startedAt, { locale });

  return <BackofficeShell user={user}>{children}</BackofficeShell>;
}
