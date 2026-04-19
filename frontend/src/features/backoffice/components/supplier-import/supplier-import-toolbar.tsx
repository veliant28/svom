import { useMemo } from "react";

import {
  SupplierCodeSwitcher,
  SupplierWorkflowTopActions,
} from "@/features/backoffice/components/suppliers/supplier-workspace-header-controls";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import type { SupplierCode } from "@/features/backoffice/hooks/use-supplier-workspace-scope";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierImportToolbar({
  activeCode,
  setActiveCode,
  hrefFor,
  onRefresh,
  t,
  tUtr,
  tGpl,
}: {
  activeCode: SupplierCode;
  setActiveCode: (next: SupplierCode) => void;
  hrefFor: (pathname: string, code?: SupplierCode) => string;
  onRefresh: () => void;
  t: Translator;
  tUtr: Translator;
  tGpl: Translator;
}) {
  const topActions = useMemo(
    () => (
      <SupplierWorkflowTopActions
        activeCode={activeCode}
        currentView="import"
        settingsHref={hrefFor("/backoffice/suppliers")}
        importHref={hrefFor("/backoffice/suppliers/import")}
        importRunsHref={hrefFor("/backoffice/suppliers/import-runs")}
        importErrorsHref={hrefFor("/backoffice/suppliers/import-errors")}
        importQualityHref={hrefFor("/backoffice/suppliers/import-quality")}
        productsHref={hrefFor("/backoffice/suppliers/products")}
        brandsHref={hrefFor("/backoffice/suppliers/brands", "utr")}
        onRefresh={onRefresh}
        settingsLabel={t("actions.settings")}
        importLabel={t("actions.import")}
        importRunsLabel={t("actions.importRuns")}
        importErrorsLabel={t("actions.importErrors")}
        importQualityLabel={t("actions.importQuality")}
        productsLabel={t("actions.products")}
        brandsLabel={t("actions.brands")}
        refreshLabel={t("actions.refreshAll")}
      />
    ),
    [activeCode, hrefFor, onRefresh, t],
  );

  const switcher = useMemo(
    () => (
      <SupplierCodeSwitcher
        activeCode={activeCode}
        onChange={setActiveCode}
        utrLabel={tUtr("label")}
        gplLabel={tGpl("label")}
        ariaLabel={t("title")}
      />
    ),
    [activeCode, setActiveCode, t, tGpl, tUtr],
  );

  return (
    <PageHeader
      title={t("importPage.title")}
      description={t("importPage.subtitle")}
      switcher={switcher}
      actions={topActions}
    />
  );
}
