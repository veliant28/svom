"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

import { BackofficeHeaderProvider } from "@/features/backoffice/components/layout/backoffice-header-context";
import { BackofficeSidebar } from "@/features/backoffice/components/layout/backoffice-sidebar";
import { BackofficeTopbar } from "@/features/backoffice/components/layout/backoffice-topbar";
import { BackofficeToastProvider } from "@/features/backoffice/components/notifications/backoffice-toast-provider";
import { usePathname, useRouter } from "@/i18n/navigation";
import type { BackofficeUser } from "@/features/backoffice/types/backoffice";

const ROUTE_PREFETCH_LIST = [
  "/backoffice/users",
  "/backoffice/groups",
  "/backoffice/brands",
  "/backoffice/categories",
  "/backoffice/footer",
  "/backoffice/suppliers",
  "/backoffice/import-schedules",
  "/backoffice/suppliers/import",
  "/backoffice/suppliers/import-runs",
  "/backoffice/suppliers/import-errors",
  "/backoffice/suppliers/import-quality",
  "/backoffice/suppliers/products",
  "/backoffice/suppliers/brands",
] as const;

const prefetchedRoutes = new Set<string>();

export function BackofficeShell({ children, user }: { children: ReactNode; user: BackofficeUser }) {
  const t = useTranslations("backoffice.common");
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    let canceled = false;
    let idleId: number | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const runPrefetch = () => {
      if (canceled) {
        return;
      }
      ROUTE_PREFETCH_LIST.forEach((route) => {
        if (prefetchedRoutes.has(route) || pathname.startsWith(route)) {
          return;
        }
        prefetchedRoutes.add(route);
        router.prefetch(route);
      });
    };

    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      idleId = window.requestIdleCallback(
        () => runPrefetch(),
        { timeout: 1500 },
      );
    } else {
      timeoutId = setTimeout(runPrefetch, 250);
    }

    return () => {
      canceled = true;
      if (idleId !== null && typeof window !== "undefined" && "cancelIdleCallback" in window) {
        window.cancelIdleCallback(idleId);
      }
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, [pathname, router]);

  return (
    <BackofficeToastProvider>
      <div className="min-h-screen lg:grid lg:grid-cols-[18rem_1fr]">
        <BackofficeSidebar
          open={sidebarOpen}
          user={user}
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
