"use client";

import { useEffect, useMemo, useState } from "react";
import { Boxes, CheckCircle2, ChevronLeft, XCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { AddToCartButton } from "@/features/cart/components/add-to-cart-button";
import { CartProductQuantityStepper } from "@/features/cart/components/cart-product-quantity-stepper";
import { getProductFitmentOptions } from "@/features/catalog/api/get-product-fitment-options";
import { getProductFitments } from "@/features/catalog/api/get-product-fitments";
import { useProductDetail } from "@/features/catalog/hooks/use-product-detail";
import { resolveCompatibilityBadgeState } from "@/features/catalog/lib/compatibility-badge";
import { buildProductIdentityParts } from "@/features/catalog/lib/product-identity";
import type { ProductFitment, ProductFitmentOptions } from "@/features/catalog/types";
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
  const { product, isLoading, vehicleParams } = useProductDetail(slug);
  const images = Array.isArray(product?.images) ? product.images : [];
  const attributes = Array.isArray(product?.attributes) ? product.attributes : [];
  const productFitments = useMemo(() => (Array.isArray(product?.fitments) ? product.fitments : []), [product?.fitments]);
  const [selectedMake, setSelectedMake] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [fitmentOptions, setFitmentOptions] = useState<ProductFitmentOptions | null>(null);
  const [remoteFitments, setRemoteFitments] = useState<ProductFitment[] | null>(null);
  const [remoteFitmentCount, setRemoteFitmentCount] = useState<number | null>(null);
  const [selectedVehicleApplied, setSelectedVehicleApplied] = useState(false);
  const [fitmentListExpanded, setFitmentListExpanded] = useState(false);
  const fitments = remoteFitments ?? productFitments;
  const catalogParams = useMemo(() => {
    const nextParams = new URLSearchParams(searchParams.toString());
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
  const stockTone: BackofficeStatusChipTone = totalStockQty <= 0 ? "red" : totalStockQty <= 5 ? "orange" : "blue";
  const fitmentBadge = (() => {
    const selectedVehicleCompatible = product?.compatibility_summary?.selected_vehicle?.is_compatible;
    const state = resolveCompatibilityBadgeState({
      fitsSelectedVehicle:
        typeof selectedVehicleCompatible === "boolean" ? selectedVehicleCompatible : product?.fits_selected_vehicle,
      hasFitmentData: (product?.compatibility_summary?.fitment_count || product?.fitment_count || 0) > 0,
      isAutoDbCompatibleDataAvailable: product?.is_autodb_compatible_data_available,
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
    setFitmentOptions(null);
    setRemoteFitments(null);
    setRemoteFitmentCount(null);
    setSelectedVehicleApplied(false);
    setFitmentListExpanded(false);
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
    if (!product) {
      return;
    }

    let isMounted = true;

    async function loadOptions() {
      try {
        const options = await getProductFitmentOptions(slug, locale, {
          ...vehicleParams,
          make: selectedMake,
          model: selectedModel,
        });
        if (isMounted) {
          setFitmentOptions(options);
        }
      } catch {
        if (isMounted) {
          setFitmentOptions(null);
        }
      }
    }

    void loadOptions();

    return () => {
      isMounted = false;
    };
  }, [locale, product, selectedMake, selectedModel, slug, vehicleParams]);

  useEffect(() => {
    if (selectedVehicleApplied || !fitmentOptions?.selected_make || !fitmentOptions.selected_model) {
      return;
    }

    setSelectedMake(fitmentOptions.selected_make);
    setSelectedModel(fitmentOptions.selected_model);
    setSelectedVehicleApplied(true);
  }, [fitmentOptions, selectedVehicleApplied]);

  useEffect(() => {
    if (!product || (!selectedMake && !selectedModel)) {
      setRemoteFitments(null);
      setRemoteFitmentCount(null);
      return;
    }

    let isMounted = true;

    async function loadRows() {
      try {
        const response = await getProductFitments(slug, locale, {
          ...vehicleParams,
          make: selectedMake,
          model: selectedModel,
          limit: 300,
        });
        if (isMounted) {
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
  }, [locale, product, selectedMake, selectedModel, slug, vehicleParams]);

  const availableMakes = useMemo(() => {
    if (fitmentOptions?.makes.length) {
      return fitmentOptions.makes.map((option) => option.value);
    }

    return Array.from(new Set(productFitments.map((fitment) => (fitment.make || "").trim()).filter(Boolean))).sort((a, b) =>
      a.localeCompare(b),
    );
  }, [fitmentOptions, productFitments]);

  const availableModels = useMemo(() => {
    if (fitmentOptions?.models.length) {
      return fitmentOptions.models.map((option) => option.value);
    }

    const filtered = selectedMake
      ? productFitments.filter((fitment) => (fitment.make || "").trim() === selectedMake)
      : productFitments;
    return Array.from(new Set(filtered.map((fitment) => (fitment.model || "").trim()).filter(Boolean))).sort((a, b) =>
      a.localeCompare(b),
    );
  }, [fitmentOptions, productFitments, selectedMake]);

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
    manufacturerArticle: product.manufacturer_article || product.article,
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
              <BackofficeStatusChip tone={stockTone} icon={Boxes} className="shrink-0">
                {t("labels.stockTotal", { count: product.total_stock_qty })}
              </BackofficeStatusChip>
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
                  {attribute.attribute_name}: {attribute.value}
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold">{t("fitmentTitle")}</h2>
              {fitmentBadge ? (
                <BackofficeStatusChip tone={fitmentBadge.tone} icon={fitmentBadge.icon} className="shrink-0">
                  {fitmentBadge.label}
                </BackofficeStatusChip>
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
                  {t("fitmentRows", { count: remoteFitmentCount ?? visibleFitments.length })}
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
