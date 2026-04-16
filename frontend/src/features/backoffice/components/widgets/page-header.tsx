import type { ReactNode } from "react";

import { useBackofficeHeader } from "@/features/backoffice/components/layout/backoffice-header-context";

export function PageHeader({
  title,
  description,
  actions,
  actionsBeforeLogout,
  switcher,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  actionsBeforeLogout?: ReactNode;
  switcher?: ReactNode;
}) {
  useBackofficeHeader({
    title,
    subtitle: description,
    actions,
    actionsBeforeLogout,
    switcher,
  });

  return null;
}
