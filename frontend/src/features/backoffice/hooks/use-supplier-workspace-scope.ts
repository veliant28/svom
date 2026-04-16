"use client";

import { useCallback } from "react";
import { useSearchParams } from "next/navigation";

import { getBackofficeSuppliers, getBackofficeSupplierWorkspace } from "@/features/backoffice/api/backoffice-api";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { usePathname, useRouter } from "@/i18n/navigation";

export type SupplierCode = "utr" | "gpl";

function normalizeSupplierCode(value: string | null): SupplierCode {
  if (value === "gpl") {
    return "gpl";
  }
  return "utr";
}

function hrefWithSupplier(pathname: string, code: SupplierCode): string {
  if (code === "utr") {
    return pathname;
  }
  return `${pathname}?supplier=${code}`;
}

export function useSupplierWorkspaceScope() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const activeCode = normalizeSupplierCode(searchParams.get("supplier"));

  const setActiveCode = useCallback(
    (code: SupplierCode) => {
      router.replace(hrefWithSupplier(pathname, code), { scroll: false });
    },
    [pathname, router],
  );

  const hrefFor = useCallback(
    (nextPathname: string, code: SupplierCode = activeCode) => hrefWithSupplier(nextPathname, code),
    [activeCode],
  );

  const suppliersQuery = useCallback((token: string) => getBackofficeSuppliers(token), []);
  const {
    token,
    data: suppliers,
    isLoading: suppliersLoading,
    error: suppliersError,
    refetch: refetchSuppliers,
  } = useBackofficeQuery(suppliersQuery, []);

  const workspaceQuery = useCallback((apiToken: string) => getBackofficeSupplierWorkspace(apiToken, activeCode), [activeCode]);
  const {
    data: workspace,
    isLoading: workspaceLoading,
    error: workspaceError,
    refetch: refetchWorkspace,
  } = useBackofficeQuery(workspaceQuery, [activeCode]);

  const refreshWorkspaceScope = useCallback(async () => {
    await Promise.all([refetchWorkspace(), refetchSuppliers()]);
  }, [refetchWorkspace, refetchSuppliers]);

  return {
    activeCode,
    setActiveCode,
    hrefFor,
    token,
    suppliers,
    workspace,
    suppliersLoading,
    workspaceLoading,
    suppliersError,
    workspaceError,
    refetchWorkspace,
    refetchSuppliers,
    refreshWorkspaceScope,
  };
}
