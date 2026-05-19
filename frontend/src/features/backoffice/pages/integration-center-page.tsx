"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { getBackofficeCatalogCategories } from "@/features/backoffice/api/backoffice-api";
import { AutoDbRemoteCard } from "@/features/backoffice/components/integration-center/autodb-remote-card";
import { IntegrationToggleItem } from "@/features/backoffice/components/integration-center/integration-toggle-item";
import { IntegrationTogglesTranslatorColumns } from "@/features/backoffice/components/integration-center/integration-toggles-translator-columns";
import { ReturnsSettingsCard } from "@/features/backoffice/components/integration-center/returns-settings-card";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useIntegrationCenterCore } from "@/features/backoffice/hooks/use-integration-center-core";
import { useIntegrationCenterReturns } from "@/features/backoffice/hooks/use-integration-center-returns";
import { buildCategoryPath, formatReturnsPhoneInput, type ToggleConfig } from "@/features/backoffice/lib/integration-center.config";
import type { BackofficeCatalogCategory } from "@/features/backoffice/types/backoffice";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { scrollDropdownOptionIntoView } from "@/features/checkout/lib/checkout-page.helpers";

type ReturnCategoryOption = { id: string; label: string };

export function IntegrationCenterPage() {
  const t = useTranslations("backoffice.common");
  const locale = useLocale();
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const core = useIntegrationCenterCore({ token, t, showApiError, showSuccess });

  const [categoryOptions, setCategoryOptions] = useState<ReturnCategoryOption[]>([]);

  useEffect(() => {
    async function loadCategories() {
      if (!token) {
        setCategoryOptions([]);
        return;
      }
      try {
        const rows: BackofficeCatalogCategory[] = [];
        let page = 1;
        while (true) {
          const chunk = await getBackofficeCatalogCategories(token, { page, page_size: 500, locale });
          rows.push(...chunk.results);
          if (rows.length >= chunk.count || chunk.results.length === 0) {
            break;
          }
          page += 1;
        }
        const byId = rows.reduce<Record<string, BackofficeCatalogCategory>>((acc, row) => {
          acc[row.id] = row;
          return acc;
        }, {});
        const options = rows
          .map((row) => ({ id: row.id, label: buildCategoryPath(row, byId, locale) }))
          .sort((left, right) => left.label.localeCompare(right.label, locale));
        setCategoryOptions(options);
      } catch {
        setCategoryOptions([]);
      }
    }
    void loadCategories();
  }, [locale, token]);

  const returns = useIntegrationCenterReturns({
    token,
    t,
    returnsSettings: core.returnsSettings,
    setReturnsSettings: core.setReturnsSettings,
    formatReturnsPhoneInput,
    patchReturnsSettings: core.patchReturnsSettings,
    categoryOptions,
  });

  useEffect(() => {
    scrollDropdownOptionIntoView(
      returns.settlementDropdownRef.current,
      returns.returnsSettlementScope,
      returns.returnsSettlementActiveIndex,
    );
  }, [
    returns.returnsSettlementActiveIndex,
    returns.returnsSettlementScope,
    returns.settlementDropdownRef,
  ]);

  useEffect(() => {
    scrollDropdownOptionIntoView(
      returns.warehouseDropdownRef.current,
      returns.returnsWarehouseScope,
      returns.returnsWarehouseActiveIndex,
    );
  }, [
    returns.returnsWarehouseActiveIndex,
    returns.returnsWarehouseScope,
    returns.warehouseDropdownRef,
  ]);

  function renderToggleItem(item: ToggleConfig) {
    const checked = Boolean(core.state?.[item.key]);
    const isUpdating = Boolean(core.updatingKeys[item.key]);
    return (
      <IntegrationToggleItem
        key={item.key}
        item={item}
        checked={checked}
        isUpdating={isUpdating}
        onToggle={() => {
          void core.handleToggle(item.key, !checked);
        }}
        t={t}
      />
    );
  }

  return (
    <AsyncState isLoading={core.isLoading} error={core.error} empty={core.isEmpty} emptyLabel={t("integrationCenter.messages.empty")}>
      <section className="grid gap-4">
        <PageHeader title={t("integrationCenter.title")} description={t("integrationCenter.subtitle")} />

        <div className="grid gap-3 xl:grid-cols-3">
          <IntegrationTogglesTranslatorColumns
            t={t}
            renderToggleItem={renderToggleItem}
            translator={core.translator}
            isUpdatingTranslatorProvider={core.isUpdatingTranslatorProvider}
            onTranslatorProvider={(provider) => {
              void core.handleTranslatorProvider(provider);
            }}
            googleApiKey={core.googleApiKey}
            setGoogleApiKey={core.setGoogleApiKey}
            isUpdatingGoogleApiKey={core.isUpdatingGoogleApiKey}
            onGoogleApiKeyCommit={() => {
              void core.handleGoogleApiKeyCommit();
            }}
          />

          <AutoDbRemoteCard
            t={t}
            autodbRemote={core.autodbRemote}
            autodbDraft={core.autodbDraft}
            copiedField={core.copiedField}
            updatingAutoDbFields={core.updatingAutoDbFields}
            isTestingAutoDbConnection={core.isTestingAutoDbConnection}
            onDraftChange={core.handleAutoDbDraftChange}
            onCommit={(field) => {
              void core.handleAutoDbRemoteCommit(field);
            }}
            onCopyField={(field, value) => {
              void core.handleCopyField(field, value);
            }}
            onTestConnection={() => {
              void core.handleAutoDbConnectionTest();
            }}
          />
        </div>

        <div className="grid gap-3">
          <ReturnsSettingsCard
            t={t}
            state={core.state}
            updatingKeys={core.updatingKeys}
            returnsSettings={core.returnsSettings}
            returnsPhoneInput={returns.returnsPhoneInput}
            returnsSettlementQuery={returns.returnsSettlementQuery}
            returnsWarehouseQuery={returns.returnsWarehouseQuery}
            returnsSettlementOptions={returns.returnsSettlementOptions}
            returnsWarehouseOptions={returns.returnsWarehouseOptions}
            isReturnsSettlementLoading={returns.isReturnsSettlementLoading}
            isReturnsWarehouseLoading={returns.isReturnsWarehouseLoading}
            isReturnsSettlementOpen={returns.isReturnsSettlementOpen}
            isReturnsWarehouseOpen={returns.isReturnsWarehouseOpen}
            returnsSettlementActiveIndex={returns.returnsSettlementActiveIndex}
            returnsWarehouseActiveIndex={returns.returnsWarehouseActiveIndex}
            settlementDropdownRef={returns.settlementDropdownRef}
            warehouseDropdownRef={returns.warehouseDropdownRef}
            returnsSettlementScope={returns.returnsSettlementScope}
            returnsWarehouseScope={returns.returnsWarehouseScope}
            returnsCategorySearch={returns.returnsCategorySearch}
            returnsCategorySuggestions={returns.returnsCategorySuggestions}
            categoryOptionById={returns.categoryOptionById}
            isUpdatingReturnsCategories={returns.isUpdatingReturnsCategories}
            onToggle={(key, enabled) => {
              void core.handleToggle(key, enabled);
            }}
            setReturnsSettings={(updater) => {
              core.setReturnsSettings((prev) => updater(prev));
            }}
            onReturnsFieldCommit={(field, value) => {
              void returns.handleReturnsFieldCommit(field, value);
            }}
            onReturnsPhoneInputChange={returns.setReturnsPhoneInput}
            onReturnsPhoneCommit={() => {
              void returns.handleReturnsPhoneCommit();
            }}
            onSettlementQueryChange={(value) => {
              returns.setIsReturnsSettlementOpen(true);
              returns.setReturnsSettlementQuery(value);
              core.setReturnsSettings((prev) => (prev ? { ...prev, returns_city_label: value } : prev));
            }}
            onSettlementOpen={() => {
              returns.setIsReturnsSettlementOpen(true);
            }}
            onSettlementBlur={(value) => {
              window.setTimeout(() => {
                returns.setIsReturnsSettlementOpen(false);
                returns.setReturnsSettlementOptions([]);
              }, 120);
              if (returns.consumeSettlementBlurSuppress()) {
                return;
              }
              void returns.handleReturnsSettlementManualCommit(value);
            }}
            onSettlementKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                returns.setIsReturnsSettlementOpen(true);
                returns.setReturnsSettlementActiveIndex((prev) => Math.min(returns.returnsSettlementOptions.length - 1, prev < 0 ? 0 : prev + 1));
                return;
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                returns.setIsReturnsSettlementOpen(true);
                returns.setReturnsSettlementActiveIndex((prev) => Math.max(0, prev < 0 ? 0 : prev - 1));
                return;
              }
              if (event.key === "Enter") {
                event.preventDefault();
                if (returns.returnsSettlementOptions.length) {
                  const nextIndex = returns.returnsSettlementActiveIndex >= 0 ? returns.returnsSettlementActiveIndex : 0;
                  const picked = returns.returnsSettlementOptions[nextIndex] || returns.returnsSettlementOptions[0];
                  if (picked) {
                    void returns.handleReturnsSettlementSelect(picked);
                  }
                } else {
                  void returns.handleReturnsSettlementManualCommit(event.currentTarget.value);
                }
              }
            }}
            onSettlementHoverIndex={(index) => {
              returns.setReturnsSettlementActiveIndex(index);
            }}
            onSettlementSelect={(row) => {
              void returns.handleReturnsSettlementSelect(row);
            }}
            onWarehouseQueryChange={(value) => {
              returns.setIsReturnsWarehouseOpen(true);
              returns.setReturnsWarehouseQuery(value);
              core.setReturnsSettings((prev) => (prev ? { ...prev, returns_np_warehouse_text: value } : prev));
            }}
            onWarehouseOpen={() => {
              returns.setIsReturnsWarehouseOpen(true);
            }}
            onWarehouseBlur={(value) => {
              window.setTimeout(() => {
                returns.setIsReturnsWarehouseOpen(false);
                returns.setReturnsWarehouseOptions([]);
              }, 120);
              void returns.handleReturnsFieldCommit("returns_np_warehouse_text", value);
            }}
            onWarehouseKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                returns.setIsReturnsWarehouseOpen(true);
                returns.setReturnsWarehouseActiveIndex((prev) => Math.min(returns.returnsWarehouseOptions.length - 1, prev < 0 ? 0 : prev + 1));
                return;
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                returns.setIsReturnsWarehouseOpen(true);
                returns.setReturnsWarehouseActiveIndex((prev) => Math.max(0, prev < 0 ? 0 : prev - 1));
                return;
              }
              if (event.key === "Enter") {
                event.preventDefault();
                if (returns.returnsWarehouseOptions.length) {
                  const nextIndex = returns.returnsWarehouseActiveIndex >= 0 ? returns.returnsWarehouseActiveIndex : 0;
                  const picked = returns.returnsWarehouseOptions[nextIndex] || returns.returnsWarehouseOptions[0];
                  if (picked) {
                    void returns.handleReturnsWarehouseSelect(picked);
                  }
                } else {
                  void returns.handleReturnsFieldCommit("returns_np_warehouse_text", event.currentTarget.value);
                }
              }
            }}
            onWarehouseHoverIndex={(index) => {
              returns.setReturnsWarehouseActiveIndex(index);
            }}
            onWarehouseSelect={(row) => {
              void returns.handleReturnsWarehouseSelect(row);
            }}
            onCategorySearchChange={returns.setReturnsCategorySearch}
            onCategoryKeyDown={(event) => {
              if (event.key === "Enter" && returns.returnsCategorySuggestions.length) {
                event.preventDefault();
                void returns.handleReturnsCategoryAdd(returns.returnsCategorySuggestions[0].id);
              }
            }}
            onCategoryAdd={(id) => {
              void returns.handleReturnsCategoryAdd(id);
            }}
            onCategoryRemove={(id) => {
              void returns.handleReturnsCategoryRemove(id);
            }}
          />
        </div>
      </section>
    </AsyncState>
  );
}
