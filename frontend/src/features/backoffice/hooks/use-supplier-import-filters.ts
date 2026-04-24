import { useCallback, useEffect, useMemo, useState } from "react";

import type { SupplierCode } from "@/features/backoffice/hooks/use-supplier-workspace-scope";
import { asStringList, parseCsvStrings } from "@/features/backoffice/lib/supplier-import/supplier-import-formatters";
import { selectedUtrFilterCount, type UtrFilterMode } from "@/features/backoffice/lib/supplier-import/supplier-import-quality";
import type { BackofficeSupplierPriceListParams } from "@/features/backoffice/types/suppliers.types";

export function useSupplierImportFilters({
  activeCode,
  supplierParams,
}: {
  activeCode: SupplierCode;
  supplierParams: BackofficeSupplierPriceListParams | null;
}) {
  const [format, setFormat] = useState("xlsx");
  const [inStockOnly, setInStockOnly] = useState(true);
  const [showScancode, setShowScancode] = useState(false);
  const [utrArticle, setUtrArticle] = useState(activeCode === "utr");
  const [utrFilterMode, setUtrFilterMode] = useState<UtrFilterMode>("all");
  const [selectedVisibleBrands, setSelectedVisibleBrands] = useState<number[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [manualModels, setManualModels] = useState("");
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  const isUtr = activeCode === "utr";
  const formats = ["xlsx"];
  const formatOptions = supplierParams?.format_options?.length
    ? (
      supplierParams.format_options
        .filter((item) => String(item.format || "").toLowerCase() === "xlsx")
    )
    : formats.map((item) => ({ format: item, caption: item }));
  const normalizedFormatOptions = formatOptions.length
    ? formatOptions
    : [{ format: "xlsx", caption: "xlsx" }];

  useEffect(() => {
    if (!supplierParams) {
      return;
    }
    setFormat("xlsx");
    setInStockOnly(Boolean(supplierParams.defaults?.in_stock));
    setShowScancode(Boolean(supplierParams.defaults?.show_scancode));
    setUtrArticle(Boolean(supplierParams.defaults?.utr_article));
  }, [supplierParams]);

  useEffect(() => {
    setUtrFilterMode("all");
    setSelectedVisibleBrands([]);
    setSelectedCategories([]);
    setSelectedModels([]);
    setUtrArticle(activeCode === "utr");
    setManualModels("");
  }, [activeCode]);

  useEffect(() => {
    if (!isUtr || supplierParams?.source !== "utr_api") {
      setSelectedVisibleBrands([]);
      setSelectedCategories([]);
      setSelectedModels([]);
      return;
    }

    if (utrFilterMode === "brands") {
      setSelectedVisibleBrands(
        Array.from(
          new Set(
            (supplierParams.visible_brands ?? [])
              .map((item) => Number(item.id))
              .filter((value) => Number.isFinite(value) && value > 0),
          ),
        ),
      );
      setSelectedCategories([]);
      setSelectedModels([]);
      setManualModels("");
      return;
    }

    if (utrFilterMode === "categories") {
      setSelectedCategories(
        asStringList(
          (supplierParams.categories ?? [])
            .map((item) => item.id?.trim())
            .filter((value): value is string => Boolean(value)),
        ),
      );
      setSelectedVisibleBrands([]);
      setSelectedModels([]);
      setManualModels("");
      return;
    }

    if (utrFilterMode === "models") {
      setSelectedModels(
        asStringList(
          (supplierParams.models ?? [])
            .map((item) => item.name?.trim())
            .filter((value): value is string => Boolean(value)),
        ),
      );
      setSelectedVisibleBrands([]);
      setSelectedCategories([]);
      return;
    }

    setSelectedVisibleBrands([]);
    setSelectedCategories([]);
    setSelectedModels([]);
    setManualModels("");
  }, [isUtr, supplierParams, utrFilterMode]);

  const effectiveVisibleBrands = useMemo(() => {
    if (!isUtr || utrFilterMode !== "brands") {
      return [];
    }
    return selectedVisibleBrands;
  }, [isUtr, selectedVisibleBrands, utrFilterMode]);

  const effectiveCategories = useMemo(() => {
    if (!isUtr || utrFilterMode !== "categories") {
      return [];
    }
    return selectedCategories;
  }, [isUtr, selectedCategories, utrFilterMode]);

  const effectiveModels = useMemo(() => {
    if (!isUtr || utrFilterMode !== "models") {
      return [];
    }
    return asStringList([...selectedModels, ...parseCsvStrings(manualModels)]);
  }, [isUtr, manualModels, selectedModels, utrFilterMode]);

  const requestPayload = useMemo(
    () => ({
      format,
      in_stock: inStockOnly,
      show_scancode: isUtr ? showScancode : false,
      utr_article: isUtr ? utrArticle : false,
      visible_brands: effectiveVisibleBrands,
      categories: effectiveCategories,
      models_filter: effectiveModels,
    }),
    [effectiveCategories, effectiveModels, effectiveVisibleBrands, format, inStockOnly, isUtr, showScancode, utrArticle],
  );

  const selectedCount = useMemo(
    () => selectedUtrFilterCount({
      visibleBrands: effectiveVisibleBrands,
      categories: effectiveCategories,
      models: effectiveModels,
    }),
    [effectiveCategories, effectiveModels, effectiveVisibleBrands],
  );

  const tokenReady = isHydrated;

  const toggleVisibleBrand = useCallback((id: number) => {
    setSelectedVisibleBrands((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }, []);

  const toggleCategory = useCallback((id: string) => {
    setSelectedCategories((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }, []);

  const toggleModel = useCallback((name: string) => {
    setSelectedModels((prev) => (prev.includes(name) ? prev.filter((item) => item !== name) : [...prev, name]));
  }, []);

  return {
    isUtr,
    tokenReady,
    format,
    setFormat,
    inStockOnly,
    setInStockOnly,
    showScancode,
    setShowScancode,
    utrArticle,
    setUtrArticle,
    utrFilterMode,
    setUtrFilterMode,
    selectedVisibleBrands,
    selectedCategories,
    selectedModels,
    manualModels,
    setManualModels,
    toggleVisibleBrand,
    toggleCategory,
    toggleModel,
    effectiveVisibleBrands,
    effectiveCategories,
    effectiveModels,
    requestPayload,
    selectedCount,
    formats,
    formatOptions: normalizedFormatOptions,
  };
}
