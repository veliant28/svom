"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Boxes, CheckCircle2, ChevronLeft, XCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { StatusChip, type StatusChipTone } from "@/features/backoffice/components/widgets/status-chip";
import { AddToCartButton } from "@/features/cart/components/add-to-cart-button";
import { CartProductQuantityStepper } from "@/features/cart/components/cart-product-quantity-stepper";
import { getProductFitmentOptions } from "@/features/catalog/api/get-product-fitment-options";
import { getProductFitments } from "@/features/catalog/api/get-product-fitments";
import { useProductDetail } from "@/features/catalog/hooks/use-product-detail";
import { resolveCompatibilityBadgeState } from "@/features/catalog/lib/compatibility-badge";
import { buildProductIdentityParts } from "@/features/catalog/lib/product-identity";
import type { ProductFitment } from "@/features/catalog/types";
import { WishlistToggleButton } from "@/features/wishlist/components/wishlist-toggle-button";
import { ContainedImagePanel } from "@/shared/components/ui/contained-image-panel";
import { clearCatalogReturnState, readCatalogReturnState } from "@/features/catalog/lib/catalog-navigation-state";
import { useRouter } from "@/i18n/navigation";

import { ProductDetailSkeleton } from "../components/product-detail-skeleton";

export function ProductDetailPage({ slug }: { slug: string }) {
  const locale = useLocale();
  const t = useTranslations("product.detail");
  const tCard = useTranslations("product.card");
  const router = useRouter();
  const searchParams = useSearchParams();
  const { product, isLoading, vehicleParams, errorKind, retryLoad } = useProductDetail(slug);
  const images = Array.isArray(product?.images) ? product.images : [];
  const attributes = Array.isArray(product?.attributes) ? product.attributes : [];
  const productFitments = useMemo(() => (Array.isArray(product?.fitments) ? product.fitments : []), [product?.fitments]);
  const [selectedMake, setSelectedMake] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [remoteFitments, setRemoteFitments] = useState<ProductFitment[] | null>(null);
  const [remoteFitmentCount, setRemoteFitmentCount] = useState<number | null>(null);
  const [optionMakes, setOptionMakes] = useState<string[]>([]);
  const [optionModels, setOptionModels] = useState<string[]>([]);
  const [selectedVehicleApplied, setSelectedVehicleApplied] = useState(false);
  const [fitmentListExpanded, setFitmentListExpanded] = useState(false);
  const fitmentModelsCacheRef = useRef<Map<string, string[]>>(new Map());
  const fitmentRowsCacheRef = useRef<Map<string, { count: number; results: ProductFitment[] }>>(new Map());
  const fitments = remoteFitments ?? productFitments;
  const catalogParams = useMemo(() => {
    const nextParams = new URLSearchParams(searchParams?.toString() ?? "");
    nextParams.delete("_cs");
    nextParams.delete("_csr");
    nextParams.delete("_cy");
    return nextParams;
  }, [searchParams]);
  const catalogQuery = catalogParams.toString();
  const backToCatalogHref = catalogQuery ? `/catalog?${catalogQuery}` : "/catalog";
  const handleBackToCatalogClick = () => {
    router.push(backToCatalogHref, { scroll: false });
  };
  const primaryImage = images.find((image) => image.is_primary) ?? images[0];
  const totalStockQty = product?.total_stock_qty ?? 0;
  const stockTone: StatusChipTone = totalStockQty <= 0 ? "red" : totalStockQty <= 5 ? "orange" : "blue";
  const fitmentBadge = (() => {
    const selectedVehicleCompatible = product?.compatibility_summary?.selected_vehicle?.is_compatible;
    const hasFitmentData = (product?.compatibility_summary?.fitment_count || product?.fitment_count || 0) > 0;
    const state = resolveCompatibilityBadgeState({
      fitsSelectedVehicle:
        typeof selectedVehicleCompatible === "boolean" ? selectedVehicleCompatible : product?.fits_selected_vehicle,
      hasFitmentData,
      isAutoDbCompatibleDataAvailable: hasFitmentData ? product?.is_autodb_compatible_data_available : false,
      suppressIncompatibleBadge: product?.vehicle_filter_policy === "show_all_with_badges",
    });

    if (state === "fits") {
      return {
        label: tCard("fitment.fits"),
        tone: "success" as const,
        icon: CheckCircle2,
      };
    }

    if (state === "not_fits") {
      return {
        label: tCard("fitment.notFits"),
        tone: "red" as const,
        icon: XCircle,
      };
    }

    if (state === "has_data") {
      return {
        label: tCard("fitment.hasData"),
        tone: "blue" as const,
        icon: CheckCircle2,
      };
    }

    return null;
  })();

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "auto" });
    }
    setSelectedMake("");
    setSelectedModel("");
    setRemoteFitments(null);
    setRemoteFitmentCount(null);
    setOptionMakes([]);
    setOptionModels([]);
    setSelectedVehicleApplied(false);
    setFitmentListExpanded(false);
    fitmentModelsCacheRef.current.clear();
    fitmentRowsCacheRef.current.clear();
  }, [product?.id]);

  useEffect(() => {
    if (!product) {
      return;
    }
    const state = readCatalogReturnState();
    if (state && state.productId !== product.id) {
      clearCatalogReturnState();
    }
  }, [product]);

  useEffect(() => {
    const selectedVehicle = product?.compatibility_summary?.selected_vehicle;
    if (selectedVehicleApplied || !selectedVehicle?.is_compatible) {
      return;
    }

    const makeName = (selectedVehicle.make || "").trim();
    const modelName = (selectedVehicle.model || "").trim();
    if (!makeName || !modelName) {
      setSelectedVehicleApplied(true);
      return;
    }

    setSelectedMake(makeName);
    setSelectedModel(modelName);
    setSelectedVehicleApplied(true);
  }, [product?.compatibility_summary?.selected_vehicle, selectedVehicleApplied]);

  useEffect(() => {
    if (!product) {
      setOptionMakes([]);
      setOptionModels([]);
      setRemoteFitments(null);
      setRemoteFitmentCount(null);
      return;
    }
    let isMounted = true;

    async function loadMakes() {
      try {
        const response = await getProductFitmentOptions(slug, locale, {
          ...vehicleParams,
        });
        if (!isMounted) {
          return;
        }
        const makes = (response.makes || []).map((item) => (item.label || item.value || "").trim()).filter(Boolean);
        setOptionMakes(makes);
        if (response.selected_make) {
          const suggestedMake = String(response.selected_make).trim();
          setSelectedMake((current) => current || suggestedMake);
        }
        if (response.selected_model) {
          const suggestedModel = String(response.selected_model).trim();
          setSelectedModel((current) => current || suggestedModel);
        }
      } catch {
        if (isMounted) {
          setOptionMakes([]);
        }
      }
    }

    void loadMakes();
    return () => {
      isMounted = false;
    };
  }, [locale, product, slug, vehicleParams]);

  useEffect(() => {
    if (!product || !selectedMake) {
      setOptionModels([]);
      return;
    }

    const cachedModels = fitmentModelsCacheRef.current.get(selectedMake);
    if (cachedModels) {
      setOptionModels(cachedModels);
      return;
    }

    let isMounted = true;
    async function loadModelsByMake() {
      try {
        const response = await getProductFitmentOptions(slug, locale, {
          ...vehicleParams,
          make: selectedMake,
        });
        if (!isMounted) {
          return;
        }
        const models = (response.models || []).map((item) => (item.label || item.value || "").trim()).filter(Boolean);
        fitmentModelsCacheRef.current.set(selectedMake, models);
        setOptionModels(models);
      } catch {
        if (isMounted) {
          setOptionModels([]);
        }
      }
    }

    void loadModelsByMake();
    return () => {
      isMounted = false;
    };
  }, [locale, product, selectedMake, slug, vehicleParams]);

  const fitmentRowsCacheKey = useMemo(() => {
    const vehicleKey =
      String(vehicleParams.passanger_car_id || "") ||
      String(vehicleParams.vehicle_id || "") ||
      String(vehicleParams.garage_vehicle || "");
    return [slug, vehicleKey, selectedMake, selectedModel].join("|");
  }, [selectedMake, selectedModel, slug, vehicleParams.garage_vehicle, vehicleParams.passanger_car_id, vehicleParams.vehicle_id]);

  useEffect(() => {
    if (!product) {
      setRemoteFitments(null);
      setRemoteFitmentCount(null);
      return;
    }

    const shouldLoadRemoteRows = fitmentListExpanded || Boolean(selectedMake) || Boolean(selectedModel);
    if (!shouldLoadRemoteRows) {
      setRemoteFitments(null);
      setRemoteFitmentCount(null);
      return;
    }

    const cachedRows = fitmentRowsCacheRef.current.get(fitmentRowsCacheKey);
    if (cachedRows) {
      setRemoteFitments(cachedRows.results);
      setRemoteFitmentCount(cachedRows.count);
      return;
    }

    let isMounted = true;

    async function loadRows() {
      try {
        const response = await getProductFitments(slug, locale, {
          ...vehicleParams,
          make: selectedMake || undefined,
          model: selectedModel || undefined,
          limit: selectedModel ? 300 : 160,
        });
        if (isMounted) {
          fitmentRowsCacheRef.current.set(fitmentRowsCacheKey, {
            count: response.count,
            results: response.results,
          });
          setRemoteFitments(response.results);
          setRemoteFitmentCount(response.count);
        }
      } catch {
        if (isMounted) {
          setRemoteFitments(null);
          setRemoteFitmentCount(null);
        }
      }
    }

    void loadRows();

    return () => {
      isMounted = false;
    };
  }, [fitmentListExpanded, fitmentRowsCacheKey, locale, product, selectedMake, selectedModel, slug, vehicleParams]);

  const availableMakes = useMemo(() => {
    if (optionMakes.length > 0) {
      return optionMakes;
    }
    return Array.from(new Set(fitments.map((fitment) => (fitment.make || "").trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b));
  }, [fitments, optionMakes]);

  const availableModels = useMemo(() => {
    if (!selectedMake) {
      return [];
    }
    if (optionModels.length > 0) {
      return optionModels;
    }
    const filtered = fitments.filter((fitment) => (fitment.make || "").trim() === selectedMake);
    return Array.from(new Set(filtered.map((fitment) => (fitment.model || "").trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b));
  }, [fitments, optionModels, selectedMake]);

  useEffect(() => {
    if (!selectedMake || availableMakes.includes(selectedMake)) {
      return;
    }
    setSelectedMake("");
  }, [availableMakes, selectedMake]);

  useEffect(() => {
    if (!selectedModel || availableModels.includes(selectedModel)) {
      return;
    }
    setSelectedModel("");
  }, [availableModels, selectedModel]);

  const visibleFitments = useMemo(() => {
    const rows = fitments.filter((fitment) => {
      const make = (fitment.make || "").trim();
      const model = (fitment.model || "").trim();
      if (selectedMake && make !== selectedMake) {
        return false;
      }
      if (selectedModel && model !== selectedModel) {
        return false;
      }
      return true;
    });
    const deduped = new Map<string, (typeof fitments)[number]>();
    for (const row of rows) {
      const key = [
        (row.make || "").trim(),
        (row.model || "").trim(),
        (row.generation || "").trim(),
        (row.modification || "").trim(),
        (row.engine || "").trim(),
      ].join("|");
      if (!deduped.has(key)) {
        deduped.set(key, row);
      }
    }
    return Array.from(deduped.values());
  }, [fitments, selectedMake, selectedModel]);

  if (isLoading && !product) {
    return <ProductDetailSkeleton />;
  }

  if (!product && errorKind !== "not_found") {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <p>{t("networkError")}</p>
        <button
          type="button"
          onClick={retryLoad}
          className="mt-3 inline-flex h-9 items-center rounded-md border px-3 text-sm font-medium transition hover:opacity-80"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--fg)" }}
        >
          {t("retry")}
        </button>
      </section>
    );
  }

  if (!product) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <p>{t("notFound")}</p>
      </section>
    );
  }

  const identityParts = buildProductIdentityParts({
    sku: product.sku,
    brandName: product.brand?.name,
    manufacturerArticle: product.article || product.manufacturer_article,
  });
  const compatibilitySummary = product.compatibility_summary;
  const selectedVehicle = compatibilitySummary?.selected_vehicle || null;
  const shownFitments = fitmentListExpanded ? visibleFitments : visibleFitments.slice(0, 10);

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <button
        type="button"
        onClick={handleBackToCatalogClick}
        className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium transition hover:opacity-80"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--fg)" }}
      >
        <ChevronLeft size={14} />
        {t("backToCatalog")}
      </button>

      <div className="mt-4 grid gap-5 rounded-xl border p-6 md:grid-cols-[1.15fr_1fr]" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <ContainedImagePanel className="aspect-[4/3] w-full rounded-lg" imageUrl={primaryImage?.image_url} alt={product.name} />

        <div>
          <h1 className="text-2xl font-semibold">{product.name}</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
            {t("skuLabel")}: {identityParts.join(" · ")}
          </p>
          <div className="mt-4 grid grid-cols-[max-content_1fr_max-content] items-center gap-3">
            <p className="text-xl font-semibold whitespace-nowrap">
              {product.final_price} {product.currency}
            </p>
            <div className="flex justify-center">
              <CartProductQuantityStepper productId={product.id} maxQuantity={product.total_stock_qty} />
            </div>
            <div className="flex justify-end">
              <StatusChip tone={stockTone} icon={Boxes} className="shrink-0">
                {t("labels.stockTotal", { count: product.total_stock_qty })}
              </StatusChip>
            </div>
          </div>
          <div className="mt-3 inline-flex gap-2">
            <AddToCartButton productId={product.id} variant="headerGreenIconLg" maxQuantity={product.total_stock_qty} />
            <WishlistToggleButton productId={product.id} variant="headerIconLg" />
          </div>
          <p className="mt-4 text-sm" style={{ color: "var(--muted)" }}>
            {product.short_description}
          </p>

          <div className="mt-5">
            <h2 className="text-sm font-semibold">{t("attributesTitle")}</h2>
            <ul className="mt-2 space-y-1 text-sm" style={{ color: "var(--muted)" }}>
              {attributes.map((attribute) => (
                <li key={attribute.id}>
                  <span className="font-semibold" style={{ color: "var(--text)" }}>
                    {attribute.attribute_name}:
                  </span>{" "}
                  <span>{attribute.value}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold">{t("fitmentTitle")}</h2>
              {fitmentBadge ? (
                <StatusChip tone={fitmentBadge.tone} icon={fitmentBadge.icon} className="shrink-0">
                  {fitmentBadge.label}
                </StatusChip>
              ) : null}
            </div>
            {selectedVehicle ? (
              <div
                className="mt-2 rounded-lg border px-3 py-2 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surfaceSubtle, var(--surface))" }}
              >
                <p className="font-medium" style={{ color: "var(--fg)" }}>
                  {selectedVehicle.is_compatible ? t("fitmentVehicleCompatible") : t("fitmentVehicleUnknown")}
                </p>
                <p style={{ color: "var(--muted)" }}>{selectedVehicle.label}</p>
                {selectedVehicle.subtitle ? <p style={{ color: "var(--muted)" }}>{selectedVehicle.subtitle}</p> : null}
              </div>
            ) : null}
            {fitments.length > 0 ? (
              <div className="mt-2 rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className="flex flex-col gap-1 text-xs">
                    {t("fitmentMakeLabel")}
                    <select
                      value={selectedMake}
                      onChange={(event) => {
                        setSelectedMake(event.target.value || "");
                        setSelectedModel("");
                      }}
                      className="h-9 rounded-md border px-2 text-sm"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    >
                      <option value="">{t("fitmentAllMakes")}</option>
                      {availableMakes.map((make) => (
                        <option key={make} value={make}>
                          {make}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-1 text-xs">
                    {t("fitmentModelLabel")}
                    <select
                      value={selectedModel}
                      onChange={(event) => {
                        setSelectedModel(event.target.value || "");
                      }}
                      disabled={!selectedMake}
                      className="h-9 rounded-md border px-2 text-sm"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    >
                      <option value="">{t("fitmentAllModels")}</option>
                      {availableModels.map((model) => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                    </select>
                  </label>

                </div>

                <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                  {t("fitmentRows", { count: remoteFitmentCount ?? product.fitment_count ?? visibleFitments.length })}
                </p>

                <div className="mt-2 max-h-60 space-y-1 overflow-auto pr-1">
                  {shownFitments.map((fitment) => (
                    <div
                      key={fitment.id}
                      className="rounded-md border px-2 py-1.5 text-xs"
                      style={{ borderColor: "var(--border)", color: "var(--muted)" }}
                    >
                      <p className="font-medium" style={{ color: "var(--fg)" }}>
                        {fitment.label || [fitment.make, fitment.model].filter(Boolean).join(" · ")}
                      </p>
                      <p>{[fitment.modification, fitment.engine, fitment.generation].filter(Boolean).join(" · ")}</p>
                    </div>
                  ))}
                </div>
                {visibleFitments.length > 10 ? (
                  <button
                    type="button"
                    className="mt-2 text-xs underline underline-offset-2"
                    style={{ color: "var(--muted)" }}
                    onClick={() => setFitmentListExpanded((value) => !value)}
                  >
                    {fitmentListExpanded ? t("fitmentShowLess") : t("fitmentShowMore")}
                  </button>
                ) : null}
              </div>
            ) : (
              <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
                {t("fitmentEmpty")}
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
