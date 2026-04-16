"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { BackofficeHeaderProvider } from "@/features/backoffice/components/layout/backoffice-header-context";
import { BackofficeSidebar } from "@/features/backoffice/components/layout/backoffice-sidebar";
import { BackofficeTopbar } from "@/features/backoffice/components/layout/backoffice-topbar";
import { BackofficeToastProvider } from "@/features/backoffice/components/notifications/backoffice-toast-provider";
import type { BackofficeUser } from "@/features/backoffice/types/backoffice";

export function BackofficeShell({ children, user }: { children: ReactNode; user: BackofficeUser }) {
  const t = useTranslations("backoffice.common");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <BackofficeToastProvider>
      <div className="min-h-screen lg:grid lg:grid-cols-[18rem_1fr]">
        <BackofficeSidebar
          open={sidebarOpen}
          onNavigate={() => {
            setSidebarOpen(false);
          }}
        />

        <div className="relative min-w-0">
          {sidebarOpen ? (
            <button
              type="button"
              className="fixed inset-0 z-10 bg-black/40 lg:hidden"
              aria-label={t("closeSidebar")}
              onClick={() => setSidebarOpen(false)}
            />
          ) : null}

          <BackofficeHeaderProvider>
            <BackofficeTopbar
              user={user}
              onToggleSidebar={() => {
                setSidebarOpen((prev) => !prev);
              }}
            />

            <main className="mx-auto w-full max-w-7xl p-4 lg:p-6">{children}</main>
          </BackofficeHeaderProvider>
        </div>
      </div>
    </BackofficeToastProvider>
  );
}
