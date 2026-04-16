"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BadgeDollarSign, CheckCircle2, Flame, ListChecks, Pencil, RefreshCw, Sparkles, Star, Trash2, type LucideIcon, XCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import {
  createBackofficeCatalogProduct,
  deleteBackofficeCatalogProduct,
  getBackofficeCatalogBrands,
  getBackofficeCatalogCategories,
  getBackofficeCatalogProducts,
  runReindexProductsAction,
  updateBackofficeCatalogProduct,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeStatusChip, type BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeCatalogBrand, BackofficeCatalogCategory, BackofficeCatalogProduct } from "@/features/backoffice/types/backoffice";
import { Link } from "@/i18n/navigation";

type ProductModalMode = "create" | "edit";
type CategoryOption = {
  id: string;
  label: string;
};

type ProductModalState = {
  sku: string;
  article: string;
  name: string;
  brand: string;
  category: string;
  is_active: boolean;
  is_featured: boolean;
  is_new: boolean;
  is_bestseller: boolean;
};

const DEFAULT_FORM_STATE: ProductModalState = {
  sku: "",
  article: "",
  name: "",
  brand: "",
  category: "",
  is_active: true,
  is_featured: false,
  is_new: false,
  is_bestseller: false,
};

type ActionIconButtonProps = {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "danger";
};

function formatProductPrice(value: string | null, currency: string | null, locale: string): string {
  const normalized = String(value ?? "").trim();
  if (!normalized) {
    return "-";
  }

  const parsed = Number(normalized);
  const amount = Number.isFinite(parsed)
    ? new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(parsed)
    : normalized;
  return `${amount} ${currency || "UAH"}`.trim();
}

type WarehouseSegment = {
  key: string;
  value: string;
  qty: number | null;
  source_code: string;
  index: number;
};

function warehouseVisualRank(qty: number | null): number {
  if (qty === null || !Number.isFinite(qty)) {
    return Number.MAX_SAFE_INTEGER;
  }
  if (qty >= 7) {
    return 1;
  }
  if (qty >= 4) {
    return 2;
  }
  if (qty >= 1) {
    return 3;
  }
  if (qty === 0) {
    return 4;
  }
  return Number.MAX_SAFE_INTEGER;
}

function resolveWarehouseTone(qty: number | null): { border: string; background: string; text: string } {
  if (qty === 0) {
    return {
      border: "#94a3b8",
      background: "#94a3b8",
      text: "#ffffff",
    };
  }
  if (qty !== null && qty > 0 && qty <= 3) {
    return {
      border: "#e11d48",
      background: "#e11d48",
      text: "#ffffff",
    };
  }
  if (qty !== null && qty >= 4 && qty <= 6) {
    return {
      border: "#f59e0b",
      background: "#f59e0b",
      text: "#111827",
    };
  }
  if (qty !== null && qty >= 7) {
    return {
      border: "#16a34a",
      background: "#16a34a",
      text: "#ffffff",
    };
  }
  return {
    border: "var(--border)",
    background: "var(--surface-2)",
    text: "var(--text)",
  };
}

function formatWarehouseQty(qty: number | null): string {
  if (qty === null) {
    return "?";
  }
  const normalized = Math.max(0, Math.trunc(qty));
  if (normalized > 99) {
    return "99+";
  }
  return String(normalized);
}

function StatusIconChip({
  label,
  tone,
  icon,
}: {
  label: string;
  tone: BackofficeStatusChipTone;
  icon: LucideIcon;
}) {
  return (
    <BackofficeTooltip
      content={label}
      placement="top"
      align="center"
      wrapperClassName="inline-flex"
      tooltipClassName="whitespace-nowrap"
    >
      <BackofficeStatusChip
        tone={tone}
        icon={icon}
        className="cursor-help justify-center gap-0 px-1.5 [&>span:last-child]:hidden"
      >
        <span className="sr-only">{label}</span>
      </BackofficeStatusChip>
    </BackofficeTooltip>
  );
}

function ActionIconButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
  tone = "default",
}: ActionIconButtonProps) {
  const isDanger = tone === "danger";

  return (
    <BackofficeTooltip
      content={label}
      placement="top"
      align="start"
      wrapperClassName="inline-flex"
      tooltipClassName="min-w-[150px]"
    >
      <button
        type="button"
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
        style={{
          borderColor: isDanger ? "#ef4444" : "var(--border)",
          backgroundColor: "var(--surface)",
          color: isDanger ? "#dc2626" : "var(--text)",
        }}
        aria-label={label}
        disabled={disabled}
        onClick={onClick}
      >
        <Icon className="h-4 w-4" />
      </button>
    </BackofficeTooltip>
  );
}

function SelectAllPageCheckbox({
  checked,
  indeterminate,
  ariaLabel,
  onChange,
}: {
  checked: boolean;
  indeterminate: boolean;
  ariaLabel: string;
  onChange: () => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!inputRef.current) {
      return;
    }
    inputRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <BackofficeTooltip
      content={ariaLabel}
      placement="bottom"
      align="center"
      wrapperClassName="inline-flex items-center justify-center"
      tooltipClassName="whitespace-nowrap normal-case"
    >
      <input
        ref={inputRef}
        type="checkbox"
        checked={checked}
        aria-label={ariaLabel}
        onChange={onChange}
      />
    </BackofficeTooltip>
  );
}

type ProductModalProps = {
  mode: ProductModalMode;
  isOpen: boolean;
  isSubmitting: boolean;
  form: ProductModalState;
  brands: BackofficeCatalogBrand[];
  categories: CategoryOption[];
  onClose: () => void;
  onSubmit: () => void;
  onChange: (next: Partial<ProductModalState>) => void;
  t: ReturnType<typeof useTranslations>;
};

type ProductDeleteModalProps = {
  isOpen: boolean;
  isSubmitting: boolean;
  productName: string;
  onConfirm: () => void;
  onClose: () => void;
  t: ReturnType<typeof useTranslations>;
};

type BulkDeleteModalProps = {
  isOpen: boolean;
  isSubmitting: boolean;
  count: number;
  onConfirm: () => void;
  onClose: () => void;
  t: ReturnType<typeof useTranslations>;
};

function ProductModal({
  mode,
  isOpen,
  isSubmitting,
  form,
  brands,
  categories,
  onClose,
  onSubmit,
  onChange,
  t,
}: ProductModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("products.actions.cancel")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-3xl rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{mode === "create" ? t("products.create.title") : t("products.edit.title")}</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("products.modal.subtitle")}</p>

        <div className="mt-3 grid gap-2 md:grid-cols-2">
          <input
            value={form.sku}
            onChange={(event) => onChange({ sku: event.target.value })}
            placeholder={t("products.fields.sku")}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          <input
            value={form.article}
            onChange={(event) => onChange({ article: event.target.value })}
            placeholder={t("products.fields.article")}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          <input
            value={form.name}
            onChange={(event) => onChange({ name: event.target.value })}
            placeholder={t("products.fields.name")}
            className="h-10 rounded-md border px-3 text-sm md:col-span-2"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          <select
            value={form.brand}
            onChange={(event) => onChange({ brand: event.target.value })}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          >
            <option value="">{t("products.fields.brand")}</option>
            {brands.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
          <select
            value={form.category}
            onChange={(event) => onChange({ category: event.target.value })}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          >
            <option value="">{t("products.fields.category")}</option>
            {categories.map((item) => (
              <option key={item.id} value={item.id}>{item.label}</option>
            ))}
          </select>
        </div>

        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => onChange({ is_active: event.target.checked })}
            />
            {t("products.flags.active")}
          </label>
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={form.is_featured}
              onChange={(event) => onChange({ is_featured: event.target.checked })}
            />
            {t("products.flags.featured")}
          </label>
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={form.is_new}
              onChange={(event) => onChange({ is_new: event.target.checked })}
            />
            {t("products.flags.new")}
          </label>
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={form.is_bestseller}
              onChange={(event) => onChange({ is_bestseller: event.target.checked })}
            />
            {t("products.flags.bestseller")}
          </label>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onSubmit}
          >
            {mode === "create" ? t("products.actions.create") : t("products.actions.save")}
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onClose}
          >
            {t("products.actions.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

function ProductDeleteModal({
  isOpen,
  isSubmitting,
  productName,
  onConfirm,
  onClose,
  t,
}: ProductDeleteModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("products.actions.cancel")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-md rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{t("products.actions.delete")}</h2>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("products.messages.deleteConfirm", { name: productName })}
        </p>
        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onConfirm}
          >
            {isSubmitting ? t("loading") : t("products.actions.delete")}
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onClose}
          >
            {t("products.actions.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

function BulkDeleteModal({
  isOpen,
  isSubmitting,
  count,
  onConfirm,
  onClose,
  t,
}: BulkDeleteModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("products.actions.cancel")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-md rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{t("products.actions.bulkDelete")}</h2>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("products.messages.bulkDeleteConfirm", { count })}
        </p>
        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onConfirm}
          >
            {isSubmitting ? t("loading") : t("products.actions.delete")}
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onClose}
          >
            {t("products.actions.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ProductsPage() {
  const t = useTranslations("backoffice.common");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const locale = useLocale();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [q, setQ] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState("");
  const [brandFilter, setBrandFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ProductModalState>(DEFAULT_FORM_STATE);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<BackofficeCatalogProduct | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [runningAction, setRunningAction] = useState<"reindex" | "delete" | null>(null);
  const [bulkActionsOpen, setBulkActionsOpen] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement | null>(null);

  const productsQuery = useCallback(
    (token: string) =>
      getBackofficeCatalogProducts(token, {
        q,
        is_active: isActiveFilter,
        brand: brandFilter,
        category: categoryFilter,
        page,
      }),
    [brandFilter, categoryFilter, isActiveFilter, page, q],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeCatalogProduct[] }>(productsQuery, [
    q,
    isActiveFilter,
    brandFilter,
    categoryFilter,
    page,
  ]);

  const brandsQuery = useCallback(async (authToken: string) => {
    const results: BackofficeCatalogBrand[] = [];
    let page = 1;

    while (true) {
      const chunk = await getBackofficeCatalogBrands(authToken, { page, page_size: 500 });
      results.push(...chunk.results);
      if (results.length >= chunk.count || chunk.results.length === 0) {
        break;
      }
      page += 1;
    }

    return { count: results.length, results };
  }, []);
  const categoriesQuery = useCallback(
    async (authToken: string) => {
      const results: BackofficeCatalogCategory[] = [];
      let page = 1;

      while (true) {
        const chunk = await getBackofficeCatalogCategories(authToken, { page, page_size: 500, locale });
        results.push(...chunk.results);
        if (results.length >= chunk.count || chunk.results.length === 0) {
          break;
        }
        page += 1;
      }

      return { count: results.length, results };
    },
    [locale],
  );

  const { data: brandsData, refetch: refetchBrands } = useBackofficeQuery<{ count: number; results: BackofficeCatalogBrand[] }>(brandsQuery, []);
  const { data: categoriesData, refetch: refetchCategories } = useBackofficeQuery<{ count: number; results: BackofficeCatalogCategory[] }>(categoriesQuery, [locale]);

  const rows = data?.results ?? [];
  const brands = brandsData?.results ?? [];
  const rawCategories = categoriesData?.results ?? [];

  const categoriesById = useMemo(
    () =>
      rawCategories.reduce<Record<string, BackofficeCatalogCategory>>((acc, item) => {
        acc[item.id] = item;
        return acc;
      }, {}),
    [rawCategories],
  );

  const getDisplayCategoryName = useCallback(
    (category: BackofficeCatalogCategory): string => {
      if (locale === "ru") {
        return category.name_ru || category.name_uk || category.name;
      }
      if (locale === "en") {
        return category.name_en || category.name_uk || category.name;
      }
      return category.name_uk || category.name;
    },
    [locale],
  );

  const buildCategoryLineage = useCallback(
    (category: BackofficeCatalogCategory): string[] => {
      const lineage: string[] = [];
      const visited = new Set<string>();
      let current: BackofficeCatalogCategory | null = category;

      while (current && !visited.has(current.id)) {
        visited.add(current.id);
        lineage.unshift(getDisplayCategoryName(current));
        if (!current.parent) {
          break;
        }
        const parentCategory: BackofficeCatalogCategory | undefined = categoriesById[current.parent];
        if (!parentCategory) {
          if (current.parent_name) {
            lineage.unshift(current.parent_name);
          }
          break;
        }
        current = parentCategory;
      }

      return lineage;
    },
    [categoriesById, getDisplayCategoryName],
  );

  const categories = useMemo<CategoryOption[]>(() => {
    const withKeys = rawCategories.map((item) => {
      const lineage = buildCategoryLineage(item);
      return {
        item,
        depth: Math.max(lineage.length - 1, 0),
        sortKey: (lineage.length ? lineage.join(" > ") : getDisplayCategoryName(item)).toLowerCase(),
      };
    });

    withKeys.sort((a, b) => a.sortKey.localeCompare(b.sortKey, locale));

    return withKeys.map(({ item, depth }) => {
      const treePrefix = depth > 0 ? `${"|    ".repeat(Math.max(0, depth - 1))}|---- ` : "";
      return {
        id: item.id,
        label: `${treePrefix}${getDisplayCategoryName(item)}`,
      };
    });
  }, [buildCategoryLineage, getDisplayCategoryName, locale, rawCategories]);
  const pagesCount = useMemo(() => Math.max(1, Math.ceil((data?.count ?? 0) / 20)), [data?.count]);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const allPageSelected = rows.length > 0 && rows.every((row) => selectedSet.has(row.id));
  const somePageSelected = rows.some((row) => selectedSet.has(row.id));

  const editingProduct = useMemo(() => rows.find((item) => item.id === editingId) ?? null, [editingId, rows]);

  const resetForm = useCallback(() => {
    setForm(DEFAULT_FORM_STATE);
  }, []);

  const openCreate = useCallback(() => {
    resetForm();
    setCreateOpen(true);
  }, [resetForm]);

  const openEdit = useCallback((item: BackofficeCatalogProduct) => {
    setEditingId(item.id);
    setForm({
      sku: item.sku,
      article: item.article,
      name: item.name,
      brand: item.brand,
      category: item.category,
      is_active: item.is_active,
      is_featured: item.is_featured,
      is_new: item.is_new,
      is_bestseller: item.is_bestseller,
    });
    setEditOpen(true);
  }, []);

  const closeCreate = useCallback(() => {
    setCreateOpen(false);
    resetForm();
  }, [resetForm]);

  const closeEdit = useCallback(() => {
    setEditOpen(false);
    setEditingId(null);
    resetForm();
  }, [resetForm]);

  const toggleSelected = useCallback((id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }, []);

  const toggleSelectAllPage = useCallback(() => {
    setSelectedIds((prev) => {
      if (rows.length === 0) {
        return prev;
      }
      const pageIds = rows.map((item) => item.id);
      const everySelected = pageIds.every((id) => prev.includes(id));
      if (everySelected) {
        return prev.filter((id) => !pageIds.includes(id));
      }
      const next = new Set(prev);
      for (const id of pageIds) {
        next.add(id);
      }
      return Array.from(next);
    });
  }, [rows]);

  const handleCreate = useCallback(async () => {
    if (!token || isSubmitting) {
      return;
    }
    if (!form.sku.trim() || !form.name.trim() || !form.brand || !form.category) {
      showApiError(new Error(t("products.messages.required")), t("products.messages.createFailed"));
      return;
    }

    setIsSubmitting(true);
    try {
      await createBackofficeCatalogProduct(token, form);
      showSuccess(t("products.messages.created"));
      closeCreate();
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("products.messages.createFailed"));
    } finally {
      setIsSubmitting(false);
    }
  }, [closeCreate, form, isSubmitting, refetch, showApiError, showSuccess, t, token]);

  const handleUpdate = useCallback(async () => {
    if (!token || !editingId || isSubmitting) {
      return;
    }
    if (!form.sku.trim() || !form.name.trim() || !form.brand || !form.category) {
      showApiError(new Error(t("products.messages.required")), t("products.messages.updateFailed"));
      return;
    }

    setIsSubmitting(true);
    try {
      await updateBackofficeCatalogProduct(token, editingId, form);
      showSuccess(t("products.messages.updated"));
      closeEdit();
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("products.messages.updateFailed"));
    } finally {
      setIsSubmitting(false);
    }
  }, [closeEdit, editingId, form, isSubmitting, refetch, showApiError, showSuccess, t, token]);

  const requestDelete = useCallback((item: BackofficeCatalogProduct) => {
    setDeleteTarget(item);
  }, []);

  const handleDelete = useCallback(
    async () => {
      if (!token || deletingId || !deleteTarget) {
        return;
      }

      setDeletingId(deleteTarget.id);
      try {
        await deleteBackofficeCatalogProduct(token, deleteTarget.id);
        showSuccess(t("products.messages.deleted"));
        setSelectedIds((prev) => prev.filter((id) => id !== deleteTarget.id));
        if (editingId === deleteTarget.id) {
          closeEdit();
        }
        setDeleteTarget(null);
        await refetch();
      } catch (actionError: unknown) {
        showApiError(actionError, t("products.messages.deleteFailed"));
      } finally {
        setDeletingId(null);
      }
    },
    [closeEdit, deleteTarget, deletingId, editingId, refetch, showApiError, showSuccess, t, token],
  );

  const runBulkReindex = useCallback(async () => {
    if (!token || selectedIds.length === 0 || runningAction) {
      return;
    }
    setRunningAction("reindex");
    try {
      await runReindexProductsAction(token, { product_ids: selectedIds, dispatch_async: true });
      showSuccess(t("products.messages.reindexQueued", { count: selectedIds.length }));
    } catch (actionError: unknown) {
      showApiError(actionError, t("products.messages.reindexFailed"));
    } finally {
      setRunningAction(null);
    }
  }, [runningAction, selectedIds, showApiError, showSuccess, t, token]);

  const runBulkDelete = useCallback(async () => {
    if (!token || selectedIds.length === 0 || runningAction) {
      if (selectedIds.length === 0) {
        setBulkDeleteOpen(false);
      }
      return;
    }
    const idsToDelete = [...selectedIds];
    setRunningAction("delete");
    try {
      let deletedCount = 0;
      for (const productId of idsToDelete) {
        try {
          await deleteBackofficeCatalogProduct(token, productId);
          deletedCount += 1;
        } catch {
          // Continue deleting the rest to avoid leaving the batch half-processed.
        }
      }

      const failedCount = idsToDelete.length - deletedCount;
      if (deletedCount > 0) {
        setSelectedIds((prev) => prev.filter((id) => !idsToDelete.includes(id)));
        if (editingId && idsToDelete.includes(editingId)) {
          closeEdit();
        }
        if (deleteTarget && idsToDelete.includes(deleteTarget.id)) {
          setDeleteTarget(null);
        }
        await refetch();
      }

      if (failedCount === 0) {
        showSuccess(t("products.messages.bulkDeleted", { count: deletedCount }));
      } else {
        showApiError(
          new Error(t("products.messages.bulkDeletePartial", { deleted: deletedCount, failed: failedCount })),
          t("products.messages.bulkDeleteFailed"),
        );
      }
    } finally {
      setRunningAction(null);
      setBulkDeleteOpen(false);
    }
  }, [closeEdit, deleteTarget, editingId, refetch, runningAction, selectedIds, showApiError, showSuccess, t, token]);

  useEffect(() => {
    if (!bulkActionsOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!bulkActionsRef.current) {
        return;
      }
      if (bulkActionsRef.current.contains(event.target as Node)) {
        return;
      }
      setBulkActionsOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setBulkActionsOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [bulkActionsOpen]);

  return (
    <section>
      <PageHeader
        title={t("products.title")}
        description={t("products.subtitle")}
        actionsBeforeLogout={(
          <button
            type="button"
            className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              void Promise.all([refetch(), refetchBrands(), refetchCategories()]);
            }}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
            {t("products.actions.refresh")}
          </button>
        )}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <BackofficeTooltip content={t("products.tooltips.openPricing")} placement="top">
              <Link
                href="/backoffice/pricing"
                className="inline-flex h-10 items-center rounded-md border px-3 text-sm font-semibold"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              >
                {t("products.actions.pricing")}
              </Link>
            </BackofficeTooltip>
          </div>
        }
      />

      <section className="mb-3 flex items-center gap-2">
        <div ref={bulkActionsRef} className="relative shrink-0">
          <BackofficeTooltip content={t("products.tooltips.bulkActions")} placement="top" tooltipClassName="whitespace-nowrap">
            <button
              type="button"
              aria-label={t("products.actions.bulkActions")}
              aria-haspopup="menu"
              aria-expanded={bulkActionsOpen}
              className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => setBulkActionsOpen((prev) => !prev)}
            >
              <ListChecks size={16} />
            </button>
          </BackofficeTooltip>
          {bulkActionsOpen ? (
            <div
              role="menu"
              className="absolute left-0 top-full z-30 mt-1 min-w-[240px] rounded-lg border p-1.5 shadow-xl"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <button
                type="button"
                role="menuitem"
                disabled={!selectedIds.length || Boolean(runningAction)}
                className="flex h-10 w-full items-center rounded-md px-3 text-left text-sm font-normal leading-5 text-slate-900 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 disabled:opacity-50"
                onClick={() => {
                  setBulkActionsOpen(false);
                  void runBulkReindex();
                }}
              >
                {runningAction === "reindex" ? t("loading") : t("products.actions.bulkReindex")}
              </button>
              <button
                type="button"
                role="menuitem"
                disabled={!selectedIds.length || Boolean(runningAction)}
                className="flex h-10 w-full items-center rounded-md px-3 text-left text-sm font-normal leading-5 text-slate-900 hover:bg-red-50 hover:text-red-700 dark:text-slate-100 dark:hover:bg-red-950/35 dark:hover:text-red-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500 disabled:opacity-50"
                onClick={() => {
                  setBulkActionsOpen(false);
                  setBulkDeleteOpen(true);
                }}
              >
                {runningAction === "delete" ? t("loading") : t("products.actions.bulkDelete")}
              </button>
            </div>
          ) : null}
        </div>
        <input
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(1);
          }}
          placeholder={t("products.filters.search")}
          className="h-10 min-w-[260px] rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={isActiveFilter}
          onChange={(event) => {
            setIsActiveFilter(event.target.value);
            setPage(1);
          }}
          className="h-10 rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("products.filters.allStates")}</option>
          <option value="true">{t("products.filters.active")}</option>
          <option value="false">{t("products.filters.inactive")}</option>
        </select>
        <select
          value={brandFilter}
          onChange={(event) => {
            setBrandFilter(event.target.value);
            setPage(1);
          }}
          className="h-10 rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("products.filters.allBrands")}</option>
          {brands.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
        <select
          value={categoryFilter}
          onChange={(event) => {
            setCategoryFilter(event.target.value);
            setPage(1);
          }}
          className="h-10 w-[210px] min-w-[210px] rounded-md border px-3 text-sm shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("products.filters.allCategories")}</option>
          {categories.map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </select>
        <button
          type="button"
          className="h-10 rounded-md border px-3 text-sm font-semibold shrink-0"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          onClick={openCreate}
        >
          {t("products.actions.create")}
        </button>
      </section>

      <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("products.states.empty")}>
        <BackofficeTable
          noHorizontalScroll
          emptyLabel={t("products.states.empty")}
          rows={rows}
          columns={[
            {
              key: "select",
              label: (
                <span className="flex items-center justify-center">
                  <SelectAllPageCheckbox
                    checked={allPageSelected}
                    indeterminate={!allPageSelected && somePageSelected}
                    ariaLabel={allPageSelected ? t("products.actions.unselectPage") : t("products.actions.selectPage")}
                    onChange={toggleSelectAllPage}
                  />
                </span>
              ),
              className: "w-[5%] text-center",
              render: (item) => (
                <div className="flex items-center justify-center">
                  <input
                    type="checkbox"
                    checked={selectedSet.has(item.id)}
                    aria-label={`${t("products.table.columns.select")}: ${item.name}`}
                    onChange={() => toggleSelected(item.id)}
                  />
                </div>
              ),
            },
            {
              key: "brand",
              label: t("products.table.columns.brand"),
              className: "w-[8%]",
              render: (item) => item.brand_name || "-",
            },
            {
              key: "product",
              label: t("products.table.columns.product"),
              className: "w-[24%]",
              render: (item) => {
                const supplierSku = (item.supplier_sku || item.sku || "").trim() || "-";
                return (
                  <div className="min-w-0">
                    <BackofficeTooltip
                      content={item.name}
                      placement="top"
                      align="start"
                      wrapperClassName="inline-flex max-w-full"
                      tooltipClassName="max-w-[320px]"
                    >
                      <span tabIndex={0} className="block truncate cursor-help font-semibold">
                        {item.name}
                      </span>
                    </BackofficeTooltip>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>
                      {t("products.fields.sku")}: {supplierSku}
                    </p>
                  </div>
                );
              },
            },
            {
              key: "price",
              label: t("products.table.columns.price"),
              className: "w-[14%]",
              render: (item) => {
                if (!item.final_price) {
                  return <span>-</span>;
                }

                const displayPrice = formatProductPrice(item.final_price, item.currency, locale);
                const supplierPrice = item.supplier_price
                  ? formatProductPrice(item.supplier_price, item.supplier_currency || item.currency, locale)
                  : "-";
                const appliedMarkup = item.applied_markup_percent ? `${item.applied_markup_percent}%` : t("products.tooltips.notSet");
                const appliedPolicyLabel = item.applied_markup_policy_scope === "global"
                  ? t("products.tooltips.policyGlobal")
                  : item.applied_markup_policy_scope === "category"
                    ? t("products.tooltips.policyCategory")
                    : item.applied_markup_policy_name || t("products.tooltips.notSet");
                const priceUpdatedAt = item.price_updated_at || item.updated_at;

                return (
                  <BackofficeTooltip
                    content={(
                      <span className="grid gap-1">
                        <span>
                          <span style={{ color: "var(--muted)" }}>{t("products.tooltips.priceWithMarkup")}:</span>{" "}
                          {displayPrice}
                        </span>
                        <span>
                          <span style={{ color: "var(--muted)" }}>{t("products.tooltips.supplierPrice")}:</span>{" "}
                          {supplierPrice}
                        </span>
                        <span>
                          <span style={{ color: "var(--muted)" }}>{t("products.tooltips.appliedMarkup")}:</span>{" "}
                          {appliedMarkup}
                        </span>
                        {item.applied_markup_policy_scope || item.applied_markup_policy_name ? (
                          <span>
                            <span style={{ color: "var(--muted)" }}>{t("products.tooltips.policy")}:</span>{" "}
                            {appliedPolicyLabel}
                          </span>
                        ) : null}
                        <span>
                          <span style={{ color: "var(--muted)" }}>{t("products.tooltips.updatedAt")}:</span>{" "}
                          {formatBackofficeDate(priceUpdatedAt)}
                        </span>
                      </span>
                    )}
                    placement="top"
                    align="start"
                    wrapperClassName="inline-flex max-w-full"
                    tooltipClassName="min-w-[220px]"
                  >
                    <BackofficeStatusChip
                      tone="blue"
                      icon={BadgeDollarSign}
                      className="w-full max-w-full min-w-0 cursor-help justify-start overflow-hidden"
                    >
                      <span className="block min-w-0 truncate tabular-nums">{displayPrice}</span>
                    </BackofficeStatusChip>
                  </BackofficeTooltip>
                );
              },
            },
            {
              key: "status",
              label: t("products.table.columns.status"),
              className: "w-[8%]",
              render: (item) => (
                <div className="flex flex-wrap gap-1">
                  <StatusIconChip
                    label={item.is_active ? t("statuses.active") : t("statuses.inactive")}
                    tone={item.is_active ? "success" : "gray"}
                    icon={item.is_active ? CheckCircle2 : XCircle}
                  />
                  {item.is_featured ? <StatusIconChip label={t("products.flags.featured")} tone="info" icon={Star} /> : null}
                  {item.is_new ? <StatusIconChip label={t("products.flags.new")} tone="orange" icon={Sparkles} /> : null}
                  {item.is_bestseller ? <StatusIconChip label={t("products.flags.bestseller")} tone="blue" icon={Flame} /> : null}
                </div>
              ),
            },
            {
              key: "warehouses",
              label: t("products.table.columns.warehouses"),
              className: "w-[32%]",
              render: (item) => {
                const warehouses = (item.warehouse_segments ?? [])
                  .map((warehouse, index) => ({
                    ...warehouse,
                    qty: (() => {
                      const normalized = warehouse.value
                        .replace(",", ".")
                        .replace(/[^\d.-]/g, "")
                        .trim();
                      if (!normalized) {
                        return null;
                      }
                      const qty = Number(normalized);
                      return Number.isFinite(qty) ? qty : null;
                    })(),
                    index,
                  }))
                  .sort((left: WarehouseSegment, right: WarehouseSegment) => {
                    const rankCompare = warehouseVisualRank(left.qty) - warehouseVisualRank(right.qty);
                    if (rankCompare !== 0) {
                      return rankCompare;
                    }
                    if (left.qty !== null && right.qty !== null) {
                      const qtyCompare = right.qty - left.qty;
                      if (qtyCompare !== 0) {
                        return qtyCompare;
                      }
                    } else if (left.qty === null && right.qty !== null) {
                      return 1;
                    } else if (left.qty !== null && right.qty === null) {
                      return -1;
                    }
                    return left.index - right.index;
                  });

                if (!warehouses.length) {
                  return <span>-</span>;
                }

                return (
                  <div className="max-w-full pb-0.5 pt-1">
                    <div
                      className="inline-flex max-w-full flex-wrap items-center gap-px rounded-[6px] border p-px"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    >
                      {warehouses.map((warehouse) => {
                        const tone = resolveWarehouseTone(warehouse.qty);
                        const supplierLabel =
                          warehouse.source_code === "utr"
                            ? tUtr("label")
                            : warehouse.source_code === "gpl"
                              ? tGpl("label")
                              : warehouse.source_code.toUpperCase();
                        const warehouseLabel = warehouse.key
                          .replace(/^count_warehouse_/i, "")
                          .replace(/^warehouse[_\s-]*/i, "")
                          .replace(/_/g, " ")
                          .trim() || "Склад";
                        const qtyLabel = formatWarehouseQty(warehouse.qty);
                        return (
                          <BackofficeTooltip
                            key={`${item.id}-warehouse-${warehouse.key}`}
                            content={(
                              <span className="grid gap-1">
                                <span className="font-semibold">{supplierLabel}</span>
                                <span>
                                  <span style={{ color: "var(--muted)" }}>{t("products.table.columns.warehouses")}:</span>{" "}
                                  {warehouseLabel}
                                </span>
                                <span>
                                  <span style={{ color: "var(--muted)" }}>{t("products.table.columns.stock")}:</span>{" "}
                                  {warehouse.value}
                                </span>
                              </span>
                            )}
                            placement="top"
                            align="start"
                            wrapperClassName="inline-flex"
                            tooltipClassName="min-w-[190px]"
                          >
                            <button
                              type="button"
                              className="inline-flex h-6 min-w-6 cursor-pointer items-center justify-center rounded-[3px] border px-1 text-[11px] font-semibold leading-none"
                              style={{
                                borderColor: tone.border,
                                backgroundColor: tone.background,
                                color: tone.text,
                              }}
                              aria-label={`${warehouseLabel}, ${t("products.table.columns.stock")}: ${warehouse.value}`}
                            >
                              {qtyLabel}
                            </button>
                          </BackofficeTooltip>
                        );
                      })}
                    </div>
                  </div>
                );
              },
            },
            {
              key: "actions",
              label: t("products.table.columns.actions"),
              className: "w-[8%] min-w-[96px] whitespace-nowrap",
              render: (item) => (
                <div className="flex items-center gap-1.5 whitespace-nowrap">
                  <ActionIconButton
                    label={t("products.tooltips.actionEdit")}
                    icon={Pencil}
                    onClick={() => openEdit(item)}
                  />
                  <ActionIconButton
                    label={deletingId === item.id ? t("loading") : t("products.tooltips.actionDelete")}
                    icon={Trash2}
                    tone="danger"
                    disabled={deletingId === item.id}
                    onClick={() => {
                      requestDelete(item);
                    }}
                  />
                </div>
              ),
            },
          ]}
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span>{t("products.pagination.total", { count: data?.count ?? 0 })}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page <= 1}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            >
              {t("products.pagination.prev")}
            </button>
            <span>{t("products.pagination.page", { current: page, total: pagesCount })}</span>
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page >= pagesCount}
              onClick={() => setPage((prev) => Math.min(pagesCount, prev + 1))}
            >
              {t("products.pagination.next")}
            </button>
          </div>
        </div>
      </AsyncState>

      <ProductModal
        mode="create"
        isOpen={createOpen}
        isSubmitting={isSubmitting}
        form={form}
        brands={brands}
        categories={categories}
        onClose={closeCreate}
        onSubmit={() => {
          void handleCreate();
        }}
        onChange={(next) => setForm((prev) => ({ ...prev, ...next }))}
        t={t}
      />

      <ProductModal
        mode="edit"
        isOpen={editOpen}
        isSubmitting={isSubmitting}
        form={form}
        brands={brands}
        categories={categories}
        onClose={closeEdit}
        onSubmit={() => {
          void handleUpdate();
        }}
        onChange={(next) => setForm((prev) => ({ ...prev, ...next }))}
        t={t}
      />

      <ProductDeleteModal
        isOpen={Boolean(deleteTarget)}
        isSubmitting={Boolean(deletingId)}
        productName={deleteTarget?.name ?? ""}
        onClose={() => {
          if (!deletingId) {
            setDeleteTarget(null);
          }
        }}
        onConfirm={() => {
          void handleDelete();
        }}
        t={t}
      />

      <BulkDeleteModal
        isOpen={bulkDeleteOpen}
        isSubmitting={runningAction === "delete"}
        count={selectedIds.length}
        onClose={() => {
          if (runningAction !== "delete") {
            setBulkDeleteOpen(false);
          }
        }}
        onConfirm={() => {
          void runBulkDelete();
        }}
        t={t}
      />

      {editOpen && !editingProduct ? (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>{t("products.states.editingUnavailable")}</p>
      ) : null}
    </section>
  );
}
