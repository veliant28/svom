"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  clearBackofficeRawOfferCategoryMapping,
  getBackofficeRawOfferCategoryMapping,
  searchBackofficeCategoryMappingCategories,
  setBackofficeRawOfferCategoryMapping,
} from "@/features/backoffice/api/backoffice-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import type {
  BackofficeCategoryMappingCategoryOption,
  BackofficeRawOfferCategoryMappingDetail,
} from "@/features/backoffice/types/backoffice";

type SupplierCategoryMappingModalProps = {
  isOpen: boolean;
  rawOfferId: string | null;
  token: string | null;
  locale: string;
  onClose: () => void;
  onSaved: () => Promise<void>;
};

export function SupplierCategoryMappingModal({
  isOpen,
  rawOfferId,
  token,
  locale,
  onClose,
  onSaved,
}: SupplierCategoryMappingModalProps) {
  const t = useTranslations("backoffice.suppliers");
  const tCommon = useTranslations("backoffice.common");
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [detail, setDetail] = useState<BackofficeRawOfferCategoryMappingDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [categories, setCategories] = useState<BackofficeCategoryMappingCategoryOption[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(false);
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (!isOpen || !rawOfferId || !token) {
      return;
    }

    let isCancelled = false;
    setDetailLoading(true);
    setDetailError(null);

    void getBackofficeRawOfferCategoryMapping(token, rawOfferId, { locale })
      .then((payload) => {
        if (isCancelled) {
          return;
        }
        setDetail(payload);
        setSelectedCategoryId(payload.mapped_category?.id ?? "");
      })
      .catch((error: unknown) => {
        if (isCancelled) {
          return;
        }
        setDetailError(showApiError(error, t("productsPage.categoryMapping.messages.loadFailed")));
      })
      .finally(() => {
        if (!isCancelled) {
          setDetailLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [isOpen, locale, rawOfferId, showApiError, t, token]);

  useEffect(() => {
    if (!isOpen || !token) {
      return;
    }

    const timer = window.setTimeout(() => {
      setCategoriesLoading(true);
      void searchBackofficeCategoryMappingCategories(token, {
        q: query,
        locale,
        page_size: 30,
      })
        .then((payload) => {
          setCategories(payload.results ?? []);
        })
        .catch((error: unknown) => {
          showApiError(error, t("productsPage.categoryMapping.messages.searchFailed"));
        })
        .finally(() => {
          setCategoriesLoading(false);
        });
    }, 220);

    return () => {
      window.clearTimeout(timer);
    };
  }, [isOpen, locale, query, showApiError, t, token]);

  const selectedCategory = useMemo(
    () => categories.find((item) => item.id === selectedCategoryId) ?? detail?.mapped_category ?? null,
    [categories, detail?.mapped_category, selectedCategoryId],
  );

  async function handleSave() {
    if (!token || !rawOfferId || !selectedCategoryId || isSaving) {
      return;
    }
    setIsSaving(true);
    try {
      await setBackofficeRawOfferCategoryMapping(token, rawOfferId, { category_id: selectedCategoryId });
      showSuccess(t("productsPage.categoryMapping.messages.saved"));
      await onSaved();
      onClose();
    } catch (error: unknown) {
      showApiError(error, t("productsPage.categoryMapping.messages.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleClear() {
    if (!token || !rawOfferId || isClearing) {
      return;
    }

    const isConfirmed = window.confirm(t("productsPage.categoryMapping.messages.clearConfirm"));
    if (!isConfirmed) {
      return;
    }

    setIsClearing(true);
    try {
      await clearBackofficeRawOfferCategoryMapping(token, rawOfferId);
      showSuccess(t("productsPage.categoryMapping.messages.cleared"));
      await onSaved();
      onClose();
    } catch (error: unknown) {
      showApiError(error, t("productsPage.categoryMapping.messages.clearFailed"));
    } finally {
      setIsClearing(false);
    }
  }

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("productsPage.categoryMapping.actions.cancel")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="supplier-category-mapping-title"
        className="relative z-10 w-full max-w-4xl rounded-xl border p-4"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        <h2 id="supplier-category-mapping-title" className="text-sm font-semibold">
          {t("productsPage.categoryMapping.title")}
        </h2>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
          {t("productsPage.categoryMapping.subtitle")}
        </p>

        <AsyncState
          isLoading={detailLoading}
          error={detailError}
          empty={!detail}
          emptyLabel={t("productsPage.categoryMapping.messages.notFound")}
        >
          {detail ? (
            <div className="mt-4 grid gap-4 lg:grid-cols-[360px_1fr]">
              <section className="rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                <div className="grid gap-2 text-sm">
                  <p><strong>{t("productsPage.categoryMapping.fields.sku")}:</strong> {detail.external_sku || "-"}</p>
                  <p><strong>{t("productsPage.categoryMapping.fields.article")}:</strong> {detail.article || "-"}</p>
                  <p><strong>{t("productsPage.categoryMapping.fields.brand")}:</strong> {detail.brand_name || "-"}</p>
                  <p><strong>{t("productsPage.categoryMapping.fields.product")}:</strong> {detail.product_name || "-"}</p>
                  <p><strong>{t("productsPage.categoryMapping.fields.supplier")}:</strong> {detail.supplier_name || detail.supplier_code}</p>
                  <p className="flex items-center gap-2">
                    <strong>{t("productsPage.categoryMapping.fields.status")}:</strong>
                    <StatusChip status={detail.category_mapping_status} />
                  </p>
                  <p>
                    <strong>{t("productsPage.categoryMapping.fields.currentCategory")}:</strong>{" "}
                    {detail.mapped_category ? detail.mapped_category.breadcrumb : t("productsPage.categoryMapping.states.notMapped")}
                  </p>
                  {detail.matched_product_category ? (
                    <p>
                      <strong>{t("productsPage.categoryMapping.fields.matchedProductCategory")}:</strong>{" "}
                      {detail.matched_product_category.breadcrumb}
                    </p>
                  ) : null}
                </div>
              </section>

              <section className="rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t("productsPage.categoryMapping.searchPlaceholder")}
                  className="h-10 w-full rounded-md border px-3 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                />

                <div className="mt-2 max-h-[320px] overflow-y-auto rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  {categoriesLoading ? (
                    <p className="text-xs" style={{ color: "var(--muted)" }}>{tCommon("loading")}</p>
                  ) : categories.length ? (
                    <div className="grid gap-2">
                      {categories.map((category) => (
                        <label
                          key={category.id}
                          className="flex cursor-pointer items-start gap-2 rounded-md border p-2"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        >
                          <input
                            type="radio"
                            name="category-choice"
                            checked={selectedCategoryId === category.id}
                            onChange={() => setSelectedCategoryId(category.id)}
                          />
                          <span>
                            <span className="block text-sm font-semibold">{category.name}</span>
                            <span className="block text-xs" style={{ color: "var(--muted)" }}>{category.breadcrumb}</span>
                            {!category.is_leaf ? (
                              <span className="mt-1 inline-block text-[11px]" style={{ color: "var(--muted)" }}>
                                {t("productsPage.categoryMapping.states.nonLeafCategory")}
                              </span>
                            ) : null}
                          </span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs" style={{ color: "var(--muted)" }}>{t("productsPage.categoryMapping.states.noCategories")}</p>
                  )}
                </div>

                <div className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                  {selectedCategory ? (
                    <span>
                      <strong>{t("productsPage.categoryMapping.fields.selectedCategory")}:</strong> {selectedCategory.breadcrumb}
                    </span>
                  ) : (
                    <span>{t("productsPage.categoryMapping.states.noSelection")}</span>
                  )}
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    className="h-9 rounded-md border px-3 text-xs font-semibold"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    disabled={!selectedCategoryId || isSaving || isClearing}
                    onClick={() => {
                      void handleSave();
                    }}
                  >
                    {isSaving ? tCommon("loading") : t("productsPage.categoryMapping.actions.save")}
                  </button>
                  {detail.mapped_category ? (
                    <button
                      type="button"
                      className="h-9 rounded-md border px-3 text-xs font-semibold"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                      disabled={isSaving || isClearing}
                      onClick={() => {
                        void handleClear();
                      }}
                    >
                      {isClearing ? tCommon("loading") : t("productsPage.categoryMapping.actions.clear")}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="h-9 rounded-md border px-3 text-xs font-semibold"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    disabled={isSaving || isClearing}
                    onClick={onClose}
                  >
                    {t("productsPage.categoryMapping.actions.cancel")}
                  </button>
                </div>
              </section>
            </div>
          ) : null}
        </AsyncState>
      </section>
    </div>
  );
}
