"use client";

import { SupplierAuthorizationCard, SupplierConnectionStatusCard } from "@/features/backoffice/components/suppliers/supplier-card";
import { SuppliersFooter } from "@/features/backoffice/components/suppliers/suppliers-list";
import { suppliersWorkspaceEmptyLabel } from "@/features/backoffice/components/suppliers/suppliers-empty-state";
import { SuppliersToolbar } from "@/features/backoffice/components/suppliers/suppliers-toolbar";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { useSuppliersPage } from "@/features/backoffice/hooks/use-suppliers-page";

export function SuppliersPage() {
  const {
    t,
    tAuth,
    tUtr,
    tGpl,
    scope,
    actions,
    login,
    setLogin,
    password,
    setPassword,
    fingerprint,
    setFingerprint,
    isEnabled,
    setIsEnabled,
    handleSaveSettings,
    accessTone,
    connectionLabel,
    tokenStateLabel,
    tokenCountdownLabel,
  } = useSuppliersPage();

  return (
    <section>
      <SuppliersToolbar
        activeCode={scope.activeCode}
        setActiveCode={scope.setActiveCode}
        hrefFor={scope.hrefFor}
        onRefresh={() => {
          void scope.refreshWorkspaceScope();
        }}
        t={t}
        tUtr={tUtr}
        tGpl={tGpl}
      />

      <AsyncState
        isLoading={scope.suppliersLoading || scope.workspaceLoading}
        error={scope.suppliersError || scope.workspaceError}
        empty={!scope.workspace}
        emptyLabel={suppliersWorkspaceEmptyLabel(t)}
      >
        {scope.workspace ? (
          <div className="grid gap-4">
            <section className="grid gap-4 lg:grid-cols-2">
              <SupplierAuthorizationCard
                tAuth={tAuth}
                activeCode={scope.activeCode}
                login={login}
                password={password}
                fingerprint={fingerprint}
                isEnabled={isEnabled}
                onLoginChange={setLogin}
                onPasswordChange={setPassword}
                onFingerprintChange={setFingerprint}
                onEnabledChange={setIsEnabled}
                onSaveSettings={() => {
                  void handleSaveSettings();
                }}
                onObtainToken={() => {
                  void actions.obtainToken();
                }}
                onRefreshToken={() => {
                  void actions.refreshToken();
                }}
                onCheckConnection={() => {
                  void actions.checkConnection();
                }}
              />

              <SupplierConnectionStatusCard
                tAuth={tAuth}
                workspace={scope.workspace}
                connectionLabel={connectionLabel}
                tokenStateLabel={tokenStateLabel}
                tokenCountdownLabel={tokenCountdownLabel}
                accessTone={accessTone}
              />
            </section>

            <SuppliersFooter
              t={t}
              suppliersCount={scope.suppliers?.length ?? 0}
            />
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
