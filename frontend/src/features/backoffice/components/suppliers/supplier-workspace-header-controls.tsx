"use client";

import { Activity, BookOpenCheck, Download, Package, ReceiptText, RefreshCw, Settings, Tags } from "lucide-react";

import { Link } from "@/i18n/navigation";

import type { SupplierCode } from "@/features/backoffice/hooks/use-supplier-workspace-scope";

const ACTION_CLASS = "inline-flex h-10 items-center rounded-md border px-4 text-sm font-semibold transition-colors";
const ACTION_STYLE = { borderColor: "var(--border)", backgroundColor: "var(--surface)" };
const ACTION_ACTIVE_STYLE = { borderColor: "var(--text)", backgroundColor: "var(--surface-2)" };

type SupplierHeaderView = "workspace" | "import" | "importRuns" | "importErrors" | "importQuality" | "products" | "brands";

export function SupplierCodeSwitcher({
  activeCode,
  onChange,
  utrLabel,
  gplLabel,
  ariaLabel,
}: {
  activeCode: SupplierCode;
  onChange: (next: SupplierCode) => void;
  utrLabel: string;
  gplLabel: string;
  ariaLabel: string;
}) {
  return (
    <div
      className="inline-flex items-center gap-2 rounded-xl border p-1"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      role="tablist"
      aria-label={ariaLabel}
    >
      <button
        type="button"
        role="tab"
        aria-selected={activeCode === "utr"}
        className="h-10 rounded-lg border px-4 text-sm transition-colors"
        style={{
          borderColor: activeCode === "utr" ? "var(--text)" : "var(--border)",
          backgroundColor: activeCode === "utr" ? "var(--surface)" : "var(--surface-2)",
          fontWeight: activeCode === "utr" ? 700 : 500,
        }}
        onClick={() => onChange("utr")}
      >
        {utrLabel}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={activeCode === "gpl"}
        className="h-10 rounded-lg border px-4 text-sm transition-colors"
        style={{
          borderColor: activeCode === "gpl" ? "var(--text)" : "var(--border)",
          backgroundColor: activeCode === "gpl" ? "var(--surface)" : "var(--surface-2)",
          fontWeight: activeCode === "gpl" ? 700 : 500,
        }}
        onClick={() => onChange("gpl")}
      >
        {gplLabel}
      </button>
    </div>
  );
}

export function SupplierWorkflowTopActions({
  activeCode,
  currentView,
  settingsHref,
  importHref,
  importRunsHref,
  importErrorsHref,
  importQualityHref,
  productsHref,
  brandsHref,
  onRefresh,
  settingsLabel,
  importLabel,
  importRunsLabel,
  importErrorsLabel,
  importQualityLabel,
  productsLabel,
  brandsLabel,
  refreshLabel,
}: {
  activeCode: SupplierCode;
  currentView: SupplierHeaderView;
  settingsHref: string;
  importHref: string;
  importRunsHref: string;
  importErrorsHref: string;
  importQualityHref: string;
  productsHref: string;
  brandsHref: string;
  onRefresh: () => void;
  settingsLabel: string;
  importLabel: string;
  importRunsLabel: string;
  importErrorsLabel: string;
  importQualityLabel: string;
  productsLabel: string;
  brandsLabel: string;
  refreshLabel: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Link
        href={settingsHref}
        className={`${ACTION_CLASS} gap-2`}
        style={currentView === "workspace" ? ACTION_ACTIVE_STYLE : ACTION_STYLE}
        aria-current={currentView === "workspace" ? "page" : undefined}
      >
        <Settings size={16} />
        {settingsLabel}
      </Link>

      <Link
        href={importHref}
        className={`${ACTION_CLASS} gap-2`}
        style={currentView === "import" ? ACTION_ACTIVE_STYLE : ACTION_STYLE}
        aria-current={currentView === "import" ? "page" : undefined}
      >
        <Download size={16} />
        {importLabel}
      </Link>

      <Link
        href={importRunsHref}
        className={`${ACTION_CLASS} gap-2`}
        style={currentView === "importRuns" ? ACTION_ACTIVE_STYLE : ACTION_STYLE}
        aria-current={currentView === "importRuns" ? "page" : undefined}
      >
        <Activity size={16} />
        {importRunsLabel}
      </Link>

      <Link
        href={importErrorsHref}
        className={`${ACTION_CLASS} gap-2`}
        style={currentView === "importErrors" ? ACTION_ACTIVE_STYLE : ACTION_STYLE}
        aria-current={currentView === "importErrors" ? "page" : undefined}
      >
        <ReceiptText size={16} />
        {importErrorsLabel}
      </Link>

      <Link
        href={importQualityHref}
        className={`${ACTION_CLASS} gap-2`}
        style={currentView === "importQuality" ? ACTION_ACTIVE_STYLE : ACTION_STYLE}
        aria-current={currentView === "importQuality" ? "page" : undefined}
      >
        <BookOpenCheck size={16} />
        {importQualityLabel}
      </Link>

      <Link
        href={productsHref}
        className={`${ACTION_CLASS} gap-2`}
        style={currentView === "products" ? ACTION_ACTIVE_STYLE : ACTION_STYLE}
        aria-current={currentView === "products" ? "page" : undefined}
      >
        <Package size={16} />
        {productsLabel}
      </Link>

      {activeCode === "utr" ? (
        <Link
          href={brandsHref}
          className={`${ACTION_CLASS} gap-2`}
          style={currentView === "brands" ? ACTION_ACTIVE_STYLE : ACTION_STYLE}
          aria-current={currentView === "brands" ? "page" : undefined}
        >
          <Tags size={16} />
          {brandsLabel}
        </Link>
      ) : null}

      <button
        type="button"
        className={`${ACTION_CLASS} gap-2`}
        style={ACTION_STYLE}
        onClick={onRefresh}
      >
        <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
        {refreshLabel}
      </button>
    </div>
  );
}
