"use client";

import { useCallback, useMemo, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  createBackofficeCatalogBrand,
  deleteBackofficeCatalogBrand,
  getBackofficeCatalogBrands,
  updateBackofficeCatalogBrand,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeCatalogBrand } from "@/features/backoffice/types/backoffice";

type BrandModalProps = {
  title: string;
  submitLabel: string;
  isOpen: boolean;
  isSubmitting: boolean;
  name: string;
  isActive: boolean;
  onNameChange: (next: string) => void;
  onIsActiveChange: (next: boolean) => void;
  onClose: () => void;
  onSubmit: () => void;
  t: ReturnType<typeof useTranslations>;
};

function BrandModal({
  title,
  submitLabel,
  isOpen,
  isSubmitting,
  name,
  isActive,
  onNameChange,
  onIsActiveChange,
  onClose,
  onSubmit,
  t,
}: BrandModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("brands.actions.cancel")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-lg rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("brands.modal.subtitle")}</p>

        <div className="mt-3 grid gap-2">
          <input
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder={t("brands.fields.name")}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={isActive}
              onChange={(event) => onIsActiveChange(event.target.checked)}
            />
            {t("brands.fields.isActive")}
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
            {submitLabel}
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            className="h-9 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={onClose}
          >
            {t("brands.actions.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

export function BrandsPage() {
  const t = useTranslations("backoffice.common");
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [query, setQuery] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState("");
  const [page, setPage] = useState(1);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createIsActive, setCreateIsActive] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingBrandId, setEditingBrandId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [deletingBrandId, setDeletingBrandId] = useState<string | null>(null);

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeCatalogBrands(token, {
        q: query,
        is_active: isActiveFilter,
        page,
      }),
    [isActiveFilter, page, query],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeCatalogBrand[] }>(queryFn, [
    query,
    isActiveFilter,
    page,
  ]);

  const rows = data?.results ?? [];
  const pagesCount = useMemo(() => {
    const total = data?.count ?? 0;
    return Math.max(1, Math.ceil(total / 20));
  }, [data?.count]);

  const editingBrand = useMemo(
    () => rows.find((item) => item.id === editingBrandId) ?? null,
    [editingBrandId, rows],
  );

  const handleCreateBrand = useCallback(async () => {
    if (!token || isCreating) {
      return;
    }
    if (!createName.trim()) {
      showApiError(new Error(t("brands.messages.nameRequired")), t("brands.messages.createFailed"));
      return;
    }

    setIsCreating(true);
    try {
      await createBackofficeCatalogBrand(token, {
        name: createName,
        is_active: createIsActive,
      });
      showSuccess(t("brands.messages.created"));
      setCreateModalOpen(false);
      setCreateName("");
      setCreateIsActive(true);
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("brands.messages.createFailed"));
    } finally {
      setIsCreating(false);
    }
  }, [createIsActive, createName, isCreating, refetch, showApiError, showSuccess, t, token]);

  const startEdit = useCallback((brand: BackofficeCatalogBrand) => {
    setEditingBrandId(brand.id);
    setEditName(brand.name);
    setEditIsActive(brand.is_active);
    setEditModalOpen(true);
  }, []);

  const handleUpdateBrand = useCallback(async () => {
    if (!token || !editingBrandId || isUpdating) {
      return;
    }
    if (!editName.trim()) {
      showApiError(new Error(t("brands.messages.nameRequired")), t("brands.messages.updateFailed"));
      return;
    }

    setIsUpdating(true);
    try {
      await updateBackofficeCatalogBrand(token, editingBrandId, {
        name: editName,
        is_active: editIsActive,
      });
      showSuccess(t("brands.messages.updated"));
      setEditModalOpen(false);
      setEditingBrandId(null);
      setEditName("");
      setEditIsActive(true);
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("brands.messages.updateFailed"));
    } finally {
      setIsUpdating(false);
    }
  }, [editIsActive, editName, editingBrandId, isUpdating, refetch, showApiError, showSuccess, t, token]);

  const handleDeleteBrand = useCallback(
    async (brand: BackofficeCatalogBrand) => {
      if (!token || deletingBrandId) {
        return;
      }

      const isConfirmed = window.confirm(t("brands.messages.deleteConfirm", { name: brand.name }));
      if (!isConfirmed) {
        return;
      }

      setDeletingBrandId(brand.id);
      try {
        await deleteBackofficeCatalogBrand(token, brand.id);
        showSuccess(t("brands.messages.deleted"));
        if (editingBrandId === brand.id) {
          setEditModalOpen(false);
          setEditingBrandId(null);
          setEditName("");
          setEditIsActive(true);
        }
        await refetch();
      } catch (actionError: unknown) {
        showApiError(actionError, t("brands.messages.deleteFailed"));
      } finally {
        setDeletingBrandId(null);
      }
    },
    [deletingBrandId, editingBrandId, refetch, showApiError, showSuccess, t, token],
  );

  return (
    <section>
      <PageHeader title={t("brands.title")} description={t("brands.subtitle")} />

      <section className="mb-3 flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(1);
          }}
          placeholder={t("brands.filters.search")}
          className="h-9 min-w-[260px] rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={isActiveFilter}
          onChange={(event) => {
            setIsActiveFilter(event.target.value);
            setPage(1);
          }}
          className="h-9 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("brands.filters.all")}</option>
          <option value="true">{t("brands.filters.active")}</option>
          <option value="false">{t("brands.filters.inactive")}</option>
        </select>
        <button
          type="button"
          className="h-9 rounded-md border px-3 text-xs font-semibold"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          onClick={() => {
            setCreateModalOpen(true);
          }}
        >
          {t("brands.actions.create")}
        </button>
      </section>

      <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("brands.states.empty")}>
        <BackofficeTable
          emptyLabel={t("brands.states.empty")}
          rows={rows}
          columns={[
            {
              key: "name",
              label: t("brands.table.columns.name"),
              render: (item) => (
                <div>
                  <p className="font-semibold">{item.name}</p>
                </div>
              ),
            },
            {
              key: "status",
              label: t("brands.table.columns.status"),
              render: (item) => (
                <BackofficeStatusChip tone={item.is_active ? "success" : "gray"} icon={item.is_active ? CheckCircle2 : XCircle}>
                  {item.is_active ? t("statuses.active") : t("statuses.inactive")}
                </BackofficeStatusChip>
              ),
            },
            { key: "updated", label: t("brands.table.columns.updated"), render: (item) => formatBackofficeDate(item.updated_at) },
            {
              key: "actions",
              label: t("brands.table.columns.actions"),
              render: (item) => (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    disabled={deletingBrandId === item.id}
                    onClick={() => startEdit(item)}
                  >
                    {t("brands.actions.edit")}
                  </button>
                  <button
                    type="button"
                    className="h-8 rounded-md border border-red-500/55 bg-red-500/12 px-2 text-xs font-semibold text-red-700 transition-colors hover:bg-red-500/20 disabled:opacity-60 dark:border-red-300/70 dark:bg-red-500/30 dark:text-red-100 dark:hover:bg-red-500/40"
                    disabled={deletingBrandId === item.id}
                    onClick={() => {
                      void handleDeleteBrand(item);
                    }}
                  >
                    {deletingBrandId === item.id ? t("loading") : t("brands.actions.delete")}
                  </button>
                </div>
              ),
            },
          ]}
        />

        <div className="mt-3 flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
          <span>{t("brands.pagination.total", { count: data?.count ?? 0 })}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page <= 1}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            >
              {t("brands.pagination.prev")}
            </button>
            <span>{t("brands.pagination.page", { current: page, total: pagesCount })}</span>
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page >= pagesCount}
              onClick={() => setPage((prev) => Math.min(pagesCount, prev + 1))}
            >
              {t("brands.pagination.next")}
            </button>
          </div>
        </div>
      </AsyncState>

      <BrandModal
        title={t("brands.create.title")}
        submitLabel={t("brands.actions.create")}
        isOpen={createModalOpen}
        isSubmitting={isCreating}
        name={createName}
        isActive={createIsActive}
        onNameChange={setCreateName}
        onIsActiveChange={setCreateIsActive}
        onClose={() => {
          if (isCreating) {
            return;
          }
          setCreateModalOpen(false);
          setCreateName("");
          setCreateIsActive(true);
        }}
        onSubmit={() => {
          void handleCreateBrand();
        }}
        t={t}
      />

      <BrandModal
        title={editingBrand ? t("brands.edit.title", { name: editingBrand.name }) : t("brands.edit.fallbackTitle")}
        submitLabel={t("brands.actions.save")}
        isOpen={editModalOpen}
        isSubmitting={isUpdating}
        name={editName}
        isActive={editIsActive}
        onNameChange={setEditName}
        onIsActiveChange={setEditIsActive}
        onClose={() => {
          if (isUpdating) {
            return;
          }
          setEditModalOpen(false);
          setEditingBrandId(null);
          setEditName("");
          setEditIsActive(true);
        }}
        onSubmit={() => {
          void handleUpdateBrand();
        }}
        t={t}
      />
    </section>
  );
}
