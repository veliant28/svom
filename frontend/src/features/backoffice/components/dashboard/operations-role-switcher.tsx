"use client";

import { Link } from "@/i18n/navigation";

import type { BackofficeStaffActivityRole } from "@/features/backoffice/types/backoffice";

export function OperationsRoleSwitcher({
  activeTab,
  dashboardHref,
  managersHref,
  operatorsHref,
  dashboardLabel,
  managersLabel,
  operatorsLabel,
  ariaLabel,
}: {
  activeTab: BackofficeStaffActivityRole | "dashboard";
  dashboardHref: string;
  managersHref: string;
  operatorsHref: string;
  dashboardLabel: string;
  managersLabel: string;
  operatorsLabel: string;
  ariaLabel: string;
}) {
  return (
    <div
      className="inline-flex items-center gap-2 rounded-xl border p-1"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      role="tablist"
      aria-label={ariaLabel}
    >
      <Link
        href={dashboardHref}
        role="tab"
        aria-selected={activeTab === "dashboard"}
        className="inline-flex h-10 items-center rounded-lg border px-4 text-sm font-semibold transition-colors"
        style={{
          borderColor: activeTab === "dashboard" ? "#16a34a" : "var(--border)",
          backgroundColor: activeTab === "dashboard" ? "#16a34a" : "var(--surface-2)",
          color: activeTab === "dashboard" ? "#ffffff" : "var(--text)",
        }}
      >
        {dashboardLabel}
      </Link>
      <Link
        href={managersHref}
        role="tab"
        aria-selected={activeTab === "manager"}
        className="inline-flex h-10 items-center rounded-lg border px-4 text-sm font-semibold transition-colors"
        style={{
          borderColor: activeTab === "manager" ? "#2563eb" : "var(--border)",
          backgroundColor: activeTab === "manager" ? "#2563eb" : "var(--surface-2)",
          color: activeTab === "manager" ? "#ffffff" : "var(--text)",
        }}
      >
        {managersLabel}
      </Link>
      <Link
        href={operatorsHref}
        role="tab"
        aria-selected={activeTab === "operator"}
        className="inline-flex h-10 items-center rounded-lg border px-4 text-sm font-semibold transition-colors"
        style={{
          borderColor: activeTab === "operator" ? "#ea580c" : "var(--border)",
          backgroundColor: activeTab === "operator" ? "#ea580c" : "var(--surface-2)",
          color: activeTab === "operator" ? "#ffffff" : "var(--text)",
        }}
      >
        {operatorsLabel}
      </Link>
    </div>
  );
}
