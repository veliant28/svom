"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { BackofficeReturnsSettingsState } from "@/features/backoffice/types/integration-center.types";
import type { CheckoutNovaPoshtaSettlement, CheckoutNovaPoshtaWarehouse } from "@/features/checkout/api/lookup-nova-poshta";
import { lookupCheckoutNovaPoshtaSettlements, lookupCheckoutNovaPoshtaWarehouses } from "@/features/checkout/api/lookup-nova-poshta";
import { formatWarehouseInputValue } from "@/features/checkout/lib/checkout-page.helpers";

type ReturnsField =
  | "returns_recipient_full_name"
  | "returns_recipient_phone"
  | "returns_city_ref"
  | "returns_city_label"
  | "returns_np_warehouse_text";

type ReturnCategoryOption = { id: string; label: string };
type Translator = (key: string, values?: Record<string, string | number>) => string;

export function useIntegrationCenterReturns({
  token,
  t,
  returnsSettings,
  setReturnsSettings,
  formatReturnsPhoneInput,
  patchReturnsSettings,
  categoryOptions,
}: {
  token: string | null;
  t: Translator;
  returnsSettings: BackofficeReturnsSettingsState | null;
  setReturnsSettings: (value: BackofficeReturnsSettingsState | null | ((prev: BackofficeReturnsSettingsState | null) => BackofficeReturnsSettingsState | null)) => void;
  formatReturnsPhoneInput: (value: string) => string;
  patchReturnsSettings: (payload: Partial<BackofficeReturnsSettingsState>, successMessage: string) => Promise<void>;
  categoryOptions: ReturnCategoryOption[];
}) {
  const [returnsCategorySearch, setReturnsCategorySearch] = useState("");
  const [returnsPhoneInput, setReturnsPhoneInput] = useState("");
  const [returnsSettlementQuery, setReturnsSettlementQuery] = useState("");
  const [returnsWarehouseQuery, setReturnsWarehouseQuery] = useState("");
  const [returnsSettlementOptions, setReturnsSettlementOptions] = useState<CheckoutNovaPoshtaSettlement[]>([]);
  const [returnsWarehouseOptions, setReturnsWarehouseOptions] = useState<CheckoutNovaPoshtaWarehouse[]>([]);
  const [isReturnsSettlementLoading, setIsReturnsSettlementLoading] = useState(false);
  const [isReturnsWarehouseLoading, setIsReturnsWarehouseLoading] = useState(false);
  const [isReturnsSettlementOpen, setIsReturnsSettlementOpen] = useState(false);
  const [isReturnsWarehouseOpen, setIsReturnsWarehouseOpen] = useState(false);
  const [returnsSettlementActiveIndex, setReturnsSettlementActiveIndex] = useState(-1);
  const [returnsWarehouseActiveIndex, setReturnsWarehouseActiveIndex] = useState(-1);
  const [updatingReturnsFields, setUpdatingReturnsFields] = useState<Record<ReturnsField, boolean>>({
    returns_recipient_full_name: false,
    returns_recipient_phone: false,
    returns_city_ref: false,
    returns_city_label: false,
    returns_np_warehouse_text: false,
  });
  const [isUpdatingReturnsCategories, setIsUpdatingReturnsCategories] = useState(false);

  const returnsSettlementScope = "returns-settlements";
  const returnsWarehouseScope = "returns-warehouses";
  const settlementDropdownRef = useRef<HTMLDivElement | null>(null);
  const warehouseDropdownRef = useRef<HTMLDivElement | null>(null);
  const suppressNextSettlementBlurCommitRef = useRef(false);

  useEffect(() => {
    if (!returnsSettings) {
      return;
    }
    setReturnsPhoneInput(formatReturnsPhoneInput(returnsSettings.returns_recipient_phone || ""));
    setReturnsSettlementQuery(returnsSettings.returns_city_label || "");
    setReturnsWarehouseQuery(returnsSettings.returns_np_warehouse_text || "");
  }, [formatReturnsPhoneInput, returnsSettings]);

  useEffect(() => {
    if (!isReturnsSettlementOpen) {
      setReturnsSettlementOptions([]);
      setIsReturnsSettlementLoading(false);
      return;
    }
    if (!token) {
      setReturnsSettlementOptions([]);
      setIsReturnsSettlementLoading(false);
      return;
    }
    const query = returnsSettlementQuery.trim();
    if (query.length < 2) {
      setReturnsSettlementOptions([]);
      setIsReturnsSettlementLoading(false);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setIsReturnsSettlementLoading(true);
      try {
        const response = await lookupCheckoutNovaPoshtaSettlements(token, { query, locale: "uk" });
        if (!cancelled) {
          setReturnsSettlementOptions(response.results.slice(0, 12));
        }
      } catch {
        if (!cancelled) {
          setReturnsSettlementOptions([]);
        }
      } finally {
        if (!cancelled) {
          setIsReturnsSettlementLoading(false);
        }
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [isReturnsSettlementOpen, returnsSettlementQuery, token]);

  useEffect(() => {
    if (!isReturnsWarehouseOpen) {
      setReturnsWarehouseOptions([]);
      setIsReturnsWarehouseLoading(false);
      return;
    }
    if (!token) {
      setReturnsWarehouseOptions([]);
      setIsReturnsWarehouseLoading(false);
      return;
    }
    const query = returnsWarehouseQuery.trim();
    const cityRef = String(returnsSettings?.returns_city_ref || "").trim();
    if (!cityRef && query.length < 1) {
      setReturnsWarehouseOptions([]);
      setIsReturnsWarehouseLoading(false);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setIsReturnsWarehouseLoading(true);
      try {
        const response = await lookupCheckoutNovaPoshtaWarehouses(token, { city_ref: cityRef, query, locale: "uk" });
        if (!cancelled) {
          setReturnsWarehouseOptions(response.results.slice(0, 18));
        }
      } catch {
        if (!cancelled) {
          setReturnsWarehouseOptions([]);
        }
      } finally {
        if (!cancelled) {
          setIsReturnsWarehouseLoading(false);
        }
      }
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [isReturnsWarehouseOpen, returnsSettings?.returns_city_ref, returnsWarehouseQuery, token]);

  useEffect(() => {
    if (!isReturnsSettlementOpen || !returnsSettlementOptions.length) {
      setReturnsSettlementActiveIndex(-1);
      return;
    }
    setReturnsSettlementActiveIndex(0);
  }, [isReturnsSettlementOpen, returnsSettlementOptions]);

  useEffect(() => {
    if (!isReturnsWarehouseOpen || !returnsWarehouseOptions.length) {
      setReturnsWarehouseActiveIndex(-1);
      return;
    }
    setReturnsWarehouseActiveIndex(0);
  }, [isReturnsWarehouseOpen, returnsWarehouseOptions]);

  const categoryOptionById = useMemo(
    () => categoryOptions.reduce<Record<string, ReturnCategoryOption>>((acc, row) => {
      acc[row.id] = row;
      return acc;
    }, {}),
    [categoryOptions],
  );
  const returnsCategorySuggestions = useMemo(() => {
    const selected = new Set(returnsSettings?.returns_non_returnable_category_ids || []);
    const query = returnsCategorySearch.trim().toLowerCase();
    const pool = categoryOptions.filter((option) => !selected.has(option.id));
    if (!query) {
      return pool.slice(0, 24);
    }
    return pool.filter((option) => option.label.toLowerCase().includes(query)).slice(0, 24);
  }, [categoryOptions, returnsCategorySearch, returnsSettings?.returns_non_returnable_category_ids]);

  async function handleReturnsFieldCommit(field: ReturnsField, value: string) {
    if (!returnsSettings || updatingReturnsFields[field]) {
      return;
    }
    const nextValue = value.trim();
    setUpdatingReturnsFields((prev) => ({ ...prev, [field]: true }));
    setReturnsSettings({ ...returnsSettings, [field]: nextValue });
    try {
      await patchReturnsSettings({ [field]: nextValue }, t("integrationCenter.messages.returnsSaved"));
    } finally {
      setUpdatingReturnsFields((prev) => ({ ...prev, [field]: false }));
    }
  }

  async function handleReturnsPhoneCommit() {
    await handleReturnsFieldCommit("returns_recipient_phone", returnsPhoneInput);
  }

  async function handleReturnsSettlementSelect(row: CheckoutNovaPoshtaSettlement) {
    if (!returnsSettings) {
      return;
    }
    suppressNextSettlementBlurCommitRef.current = true;
    const settlementLabel = String(row.label || "").trim();
    const cityRef = String(row.delivery_city_ref || row.settlement_ref || row.ref || "").trim();
    const regionLabel = String(row.area || row.region || "").trim();
    setIsReturnsSettlementOpen(false);
    setReturnsSettlementActiveIndex(-1);
    setReturnsSettlementQuery(settlementLabel);
    setReturnsSettlementOptions([]);
    setIsReturnsWarehouseOpen(false);
    setReturnsWarehouseQuery("");
    setReturnsWarehouseOptions([]);
    setReturnsSettings((prev) => (
      prev
        ? {
            ...prev,
            returns_city_label: settlementLabel,
            returns_city_ref: cityRef,
            returns_region_label: regionLabel || prev.returns_region_label,
            returns_region_ref: regionLabel || prev.returns_region_ref,
            returns_np_warehouse_text: "",
          }
        : prev
    ));
    await patchReturnsSettings(
      {
        returns_city_label: settlementLabel,
        returns_city_ref: cityRef,
        returns_np_warehouse_text: "",
        ...(regionLabel ? { returns_region_label: regionLabel, returns_region_ref: regionLabel } : {}),
      },
      t("integrationCenter.messages.returnsSaved"),
    );
  }

  async function handleReturnsWarehouseSelect(row: CheckoutNovaPoshtaWarehouse) {
    if (!returnsSettings) {
      return;
    }
    const warehouseValue = formatWarehouseInputValue(row, "uk");
    setIsReturnsWarehouseOpen(false);
    setReturnsWarehouseActiveIndex(-1);
    setReturnsWarehouseQuery(warehouseValue);
    setReturnsWarehouseOptions([]);
    setReturnsSettings((prev) => (prev ? { ...prev, returns_np_warehouse_text: warehouseValue } : prev));
    await patchReturnsSettings({ returns_np_warehouse_text: warehouseValue }, t("integrationCenter.messages.returnsSaved"));
  }

  async function handleReturnsSettlementManualCommit(value: string) {
    if (!returnsSettings) {
      return;
    }
    const nextLabel = value.trim();
    const currentLabel = String(returnsSettings.returns_city_label || "").trim();
    setIsReturnsSettlementOpen(false);
    setReturnsSettlementActiveIndex(-1);
    if (nextLabel === currentLabel) {
      return;
    }
    setReturnsSettings((prev) => (prev ? { ...prev, returns_city_label: nextLabel, returns_city_ref: "" } : prev));
    await patchReturnsSettings({ returns_city_label: nextLabel, returns_city_ref: "" }, t("integrationCenter.messages.returnsSaved"));
  }

  async function handleReturnsCategoryAdd(categoryId: string) {
    if (!returnsSettings || isUpdatingReturnsCategories) {
      return;
    }
    const nextId = categoryId.trim();
    if (!nextId || returnsSettings.returns_non_returnable_category_ids.includes(nextId)) {
      return;
    }
    setIsUpdatingReturnsCategories(true);
    const nextValues = [...returnsSettings.returns_non_returnable_category_ids, nextId];
    setReturnsSettings({ ...returnsSettings, returns_non_returnable_category_ids: nextValues });
    try {
      await patchReturnsSettings({ returns_non_returnable_category_ids: nextValues }, t("integrationCenter.messages.returnsCategoryAdded"));
      setReturnsCategorySearch("");
    } finally {
      setIsUpdatingReturnsCategories(false);
    }
  }

  async function handleReturnsCategoryRemove(categoryId: string) {
    if (!returnsSettings || isUpdatingReturnsCategories) {
      return;
    }
    setIsUpdatingReturnsCategories(true);
    const nextValues = returnsSettings.returns_non_returnable_category_ids.filter((value) => value !== categoryId);
    setReturnsSettings({ ...returnsSettings, returns_non_returnable_category_ids: nextValues });
    try {
      await patchReturnsSettings({ returns_non_returnable_category_ids: nextValues }, t("integrationCenter.messages.returnsCategoryRemoved"));
    } finally {
      setIsUpdatingReturnsCategories(false);
    }
  }

  function consumeSettlementBlurSuppress(): boolean {
    if (!suppressNextSettlementBlurCommitRef.current) {
      return false;
    }
    suppressNextSettlementBlurCommitRef.current = false;
    return true;
  }

  return {
    returnsCategorySearch,
    setReturnsCategorySearch,
    returnsPhoneInput,
    setReturnsPhoneInput,
    returnsSettlementQuery,
    setReturnsSettlementQuery,
    returnsWarehouseQuery,
    setReturnsWarehouseQuery,
    returnsSettlementOptions,
    setReturnsSettlementOptions,
    returnsWarehouseOptions,
    setReturnsWarehouseOptions,
    isReturnsSettlementLoading,
    isReturnsWarehouseLoading,
    isReturnsSettlementOpen,
    setIsReturnsSettlementOpen,
    isReturnsWarehouseOpen,
    setIsReturnsWarehouseOpen,
    returnsSettlementActiveIndex,
    setReturnsSettlementActiveIndex,
    returnsWarehouseActiveIndex,
    setReturnsWarehouseActiveIndex,
    returnsSettlementScope,
    returnsWarehouseScope,
    settlementDropdownRef,
    warehouseDropdownRef,
    suppressNextSettlementBlurCommitRef,
    consumeSettlementBlurSuppress,
    categoryOptionById,
    returnsCategorySuggestions,
    isUpdatingReturnsCategories,
    handleReturnsFieldCommit,
    handleReturnsPhoneCommit,
    handleReturnsSettlementSelect,
    handleReturnsWarehouseSelect,
    handleReturnsSettlementManualCommit,
    handleReturnsCategoryAdd,
    handleReturnsCategoryRemove,
  };
}
