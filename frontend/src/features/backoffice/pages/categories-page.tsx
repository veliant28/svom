"use client";

import { useCallback, useMemo, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import {
  createBackofficeCatalogCategory,
  deleteBackofficeCatalogCategory,
  getBackofficeCatalogCategories,
  updateBackofficeCatalogCategory,
} from "@/features/backoffice/api/backoffice-api";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeCatalogCategory } from "@/features/backoffice/types/backoffice";

type CategoryModalProps = {
  title: string;
  submitLabel: string;
  isOpen: boolean;
  isSubmitting: boolean;
  name: string;
  parentId: string;
  isActive: boolean;
  parentOptions: BackofficeCatalogCategory[];
  disabledParentIds?: Set<string>;
  getParentOptionLabel: (category: BackofficeCatalogCategory) => string;
  onNameChange: (next: string) => void;
  onParentChange: (next: string) => void;
  onIsActiveChange: (next: boolean) => void;
  onClose: () => void;
  onSubmit: () => void;
  t: ReturnType<typeof useTranslations>;
};

function CategoryModal({
  title,
  submitLabel,
  isOpen,
  isSubmitting,
  name,
  parentId,
  isActive,
  parentOptions,
  disabledParentIds,
  getParentOptionLabel,
  onNameChange,
  onParentChange,
  onIsActiveChange,
  onClose,
  onSubmit,
  t,
}: CategoryModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={t("categories.actions.cancel")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-xl rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("categories.modal.subtitle")}</p>

        <div className="mt-3 grid gap-2">
          <input
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder={t("categories.fields.name")}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
          <select
            value={parentId}
            onChange={(event) => onParentChange(event.target.value)}
            className="h-10 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          >
            <option value="">{t("categories.fields.parentNone")}</option>
            {parentOptions.map((item) => (
              <option key={item.id} value={item.id} disabled={Boolean(disabledParentIds?.has(item.id))}>
                {getParentOptionLabel(item)}
              </option>
            ))}
          </select>
          <label className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <input
              type="checkbox"
              checked={isActive}
              onChange={(event) => onIsActiveChange(event.target.checked)}
            />
            {t("categories.fields.isActive")}
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
            {t("categories.actions.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

export function CategoriesPage() {
  const t = useTranslations("backoffice.common");
  const locale = useLocale();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [query, setQuery] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState("");
  const [parentFilter, setParentFilter] = useState("");
  const [page, setPage] = useState(1);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createParentId, setCreateParentId] = useState("");
  const [createIsActive, setCreateIsActive] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editParentId, setEditParentId] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [deletingCategoryId, setDeletingCategoryId] = useState<string | null>(null);

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeCatalogCategories(token, {
        locale,
        q: query,
        is_active: isActiveFilter,
        parent: parentFilter,
        page,
      }),
    [isActiveFilter, locale, page, parentFilter, query],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeCatalogCategory[] }>(queryFn, [
    query,
    isActiveFilter,
    parentFilter,
    page,
    locale,
  ]);

  const parentOptionsQueryFn = useCallback(
    (tokenValue: string) => getBackofficeCatalogCategories(tokenValue, { page_size: 500, locale }),
    [locale],
  );

  const { data: parentOptionsData } = useBackofficeQuery<{ count: number; results: BackofficeCatalogCategory[] }>(
    parentOptionsQueryFn,
    [],
  );

  const rows = data?.results ?? [];
  const parentOptions = parentOptionsData?.results ?? [];
  const parentById = useMemo(
    () =>
      parentOptions.reduce<Record<string, BackofficeCatalogCategory>>((acc, item) => {
        acc[item.id] = item;
        return acc;
      }, {}),
    [parentOptions],
  );

  const getDisplayName = useCallback(
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

  const getDisplayParentName = useCallback(
    (category: BackofficeCatalogCategory): string => {
      if (!category.parent) {
        return "";
      }
      const parentCategory = parentById[category.parent];
      if (!parentCategory) {
        return category.parent_name;
      }
      return getDisplayName(parentCategory);
    },
    [getDisplayName, parentById],
  );

  const buildCategoryLineage = useCallback(
    (category: BackofficeCatalogCategory): string[] => {
      const lineage: string[] = [];
      const visited = new Set<string>();
      let current: BackofficeCatalogCategory | null = category;

      while (current && !visited.has(current.id)) {
        visited.add(current.id);
        lineage.unshift(getDisplayName(current));
        if (!current.parent) {
          break;
        }
        const parentCategory: BackofficeCatalogCategory | undefined = parentById[current.parent];
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
    [getDisplayName, parentById],
  );

  const getParentOptionLabel = useCallback(
    (category: BackofficeCatalogCategory): string => {
      const lineage = buildCategoryLineage(category);
      const depth = Math.max(lineage.length - 1, 0);
      const treePrefix = depth > 0 ? `${"|    ".repeat(Math.max(0, depth - 1))}|---- ` : "";
      return `${treePrefix}${getDisplayName(category)}`;
    },
    [buildCategoryLineage, getDisplayName],
  );

  const sortedParentOptions = useMemo(() => {
    const withKeys = parentOptions.map((item) => {
      const lineage = buildCategoryLineage(item);
      return {
        item,
        sortKey: (lineage.length ? lineage.join(" > ") : getDisplayName(item)).toLowerCase(),
      };
    });

    withKeys.sort((a, b) => a.sortKey.localeCompare(b.sortKey, locale));
    return withKeys.map((entry) => entry.item);
  }, [buildCategoryLineage, getDisplayName, locale, parentOptions]);

  const pagesCount = useMemo(() => {
    const total = data?.count ?? 0;
    return Math.max(1, Math.ceil(total / 20));
  }, [data?.count]);

  const editingCategory = useMemo(
    () => rows.find((item) => item.id === editingCategoryId) ?? parentOptions.find((item) => item.id === editingCategoryId) ?? null,
    [editingCategoryId, parentOptions, rows],
  );

  const childIdsByParentId = useMemo(() => {
    return parentOptions.reduce<Record<string, string[]>>((acc, item) => {
      if (!item.parent) {
        return acc;
      }
      if (!acc[item.parent]) {
        acc[item.parent] = [];
      }
      acc[item.parent].push(item.id);
      return acc;
    }, {});
  }, [parentOptions]);

  const disabledParentIds = useMemo(() => {
    const ids = new Set<string>();
    if (!editingCategoryId) {
      return ids;
    }

    ids.add(editingCategoryId);

    const queue: string[] = [editingCategoryId];
    while (queue.length > 0) {
      const currentId = queue.shift();
      if (!currentId) {
        continue;
      }

      const children = childIdsByParentId[currentId] ?? [];
      for (const childId of children) {
        if (ids.has(childId)) {
          continue;
        }
        ids.add(childId);
        queue.push(childId);
      }
    }

    return ids;
  }, [childIdsByParentId, editingCategoryId]);

  const handleCreateCategory = useCallback(async () => {
    if (!token || isCreating) {
      return;
    }
    if (!createName.trim()) {
      showApiError(new Error(t("categories.messages.nameRequired")), t("categories.messages.createFailed"));
      return;
    }

    setIsCreating(true);
    try {
      await createBackofficeCatalogCategory(token, {
        name: createName,
        parent: createParentId || null,
        is_active: createIsActive,
      });
      showSuccess(t("categories.messages.created"));
      setCreateModalOpen(false);
      setCreateName("");
      setCreateParentId("");
      setCreateIsActive(true);
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("categories.messages.createFailed"));
    } finally {
      setIsCreating(false);
    }
  }, [createIsActive, createName, createParentId, isCreating, refetch, showApiError, showSuccess, t, token]);

  const startEdit = useCallback((category: BackofficeCatalogCategory) => {
    setEditingCategoryId(category.id);
    setEditName(category.name);
    setEditParentId(category.parent ?? "");
    setEditIsActive(category.is_active);
    setEditModalOpen(true);
  }, []);

  const handleUpdateCategory = useCallback(async () => {
    if (!token || !editingCategoryId || isUpdating) {
      return;
    }
    if (!editName.trim()) {
      showApiError(new Error(t("categories.messages.nameRequired")), t("categories.messages.updateFailed"));
      return;
    }

    setIsUpdating(true);
    try {
      await updateBackofficeCatalogCategory(token, editingCategoryId, {
        name: editName,
        parent: editParentId || null,
        is_active: editIsActive,
      });
      showSuccess(t("categories.messages.updated"));
      setEditModalOpen(false);
      setEditingCategoryId(null);
      setEditName("");
      setEditParentId("");
      setEditIsActive(true);
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("categories.messages.updateFailed"));
    } finally {
      setIsUpdating(false);
    }
  }, [editIsActive, editName, editParentId, editingCategoryId, isUpdating, refetch, showApiError, showSuccess, t, token]);

  const handleDeleteCategory = useCallback(
    async (category: BackofficeCatalogCategory) => {
      if (!token || deletingCategoryId) {
        return;
      }

      const isConfirmed = window.confirm(t("categories.messages.deleteConfirm", { name: getDisplayName(category) }));
      if (!isConfirmed) {
        return;
      }

      setDeletingCategoryId(category.id);
      try {
        await deleteBackofficeCatalogCategory(token, category.id);
        showSuccess(t("categories.messages.deleted"));
        if (editingCategoryId === category.id) {
          setEditModalOpen(false);
          setEditingCategoryId(null);
          setEditName("");
          setEditParentId("");
          setEditIsActive(true);
        }
        await refetch();
      } catch (actionError: unknown) {
        showApiError(actionError, t("categories.messages.deleteFailed"));
      } finally {
        setDeletingCategoryId(null);
      }
    },
    [deletingCategoryId, editingCategoryId, getDisplayName, refetch, showApiError, showSuccess, t, token],
  );

  return (
    <section>
      <PageHeader title={t("categories.title")} />

      <section className="mb-3 flex flex-wrap items-center gap-2 lg:flex-nowrap">
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(1);
          }}
          placeholder={t("categories.filters.search")}
          className="h-9 min-w-[220px] flex-1 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
        <select
          value={isActiveFilter}
          onChange={(event) => {
            setIsActiveFilter(event.target.value);
            setPage(1);
          }}
          className="h-9 w-[170px] shrink-0 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("categories.filters.all")}</option>
          <option value="true">{t("categories.filters.active")}</option>
          <option value="false">{t("categories.filters.inactive")}</option>
        </select>
        <select
          value={parentFilter}
          onChange={(event) => {
            setParentFilter(event.target.value);
            setPage(1);
          }}
          className="h-9 min-w-[220px] flex-1 rounded-md border px-3 text-sm"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <option value="">{t("categories.filters.anyParent")}</option>
          <option value="root">{t("categories.filters.rootOnly")}</option>
          {sortedParentOptions.map((item) => (
            <option key={item.id} value={item.id}>{getParentOptionLabel(item)}</option>
          ))}
        </select>
        <button
          type="button"
          className="h-9 shrink-0 rounded-md border px-3 text-xs font-semibold"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          onClick={() => {
            setCreateModalOpen(true);
          }}
        >
          {t("categories.actions.create")}
        </button>
      </section>

      <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("categories.states.empty")}>
        <BackofficeTable
          emptyLabel={t("categories.states.empty")}
          rows={rows}
          columns={[
            {
              key: "name",
              label: t("categories.table.columns.name"),
              render: (item) => (
                <div>
                  <p className="font-semibold">{getDisplayName(item)}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>{getDisplayParentName(item) || t("categories.table.rootLabel")}</p>
                </div>
              ),
            },
            {
              key: "status",
              label: t("categories.table.columns.status"),
              render: (item) => (
                <BackofficeStatusChip tone={item.is_active ? "success" : "gray"} icon={item.is_active ? CheckCircle2 : XCircle}>
                  {item.is_active ? t("statuses.active") : t("statuses.inactive")}
                </BackofficeStatusChip>
              ),
            },
            { key: "updated", label: t("categories.table.columns.updated"), render: (item) => formatBackofficeDate(item.updated_at) },
            {
              key: "actions",
              label: t("categories.table.columns.actions"),
              render: (item) => (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="h-8 rounded-md border px-2 text-xs"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    disabled={deletingCategoryId === item.id}
                    onClick={() => startEdit(item)}
                  >
                    {t("categories.actions.edit")}
                  </button>
                  <button
                    type="button"
                    className="h-8 rounded-md border border-red-500/55 bg-red-500/12 px-2 text-xs font-semibold text-red-700 transition-colors hover:bg-red-500/20 disabled:opacity-60 dark:border-red-300/70 dark:bg-red-500/30 dark:text-red-100 dark:hover:bg-red-500/40"
                    disabled={deletingCategoryId === item.id}
                    onClick={() => {
                      void handleDeleteCategory(item);
                    }}
                  >
                    {deletingCategoryId === item.id ? t("loading") : t("categories.actions.delete")}
                  </button>
                </div>
              ),
            },
          ]}
        />

        <div className="mt-3 flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
          <span>{t("categories.pagination.total", { count: data?.count ?? 0 })}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page <= 1}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            >
              {t("categories.pagination.prev")}
            </button>
            <span>{t("categories.pagination.page", { current: page, total: pagesCount })}</span>
            <button
              type="button"
              className="h-8 rounded-md border px-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              disabled={page >= pagesCount}
              onClick={() => setPage((prev) => Math.min(pagesCount, prev + 1))}
            >
              {t("categories.pagination.next")}
            </button>
          </div>
        </div>
      </AsyncState>

      <CategoryModal
        title={t("categories.create.title")}
        submitLabel={t("categories.actions.create")}
        isOpen={createModalOpen}
        isSubmitting={isCreating}
        name={createName}
        parentId={createParentId}
        isActive={createIsActive}
        parentOptions={sortedParentOptions}
        getParentOptionLabel={getParentOptionLabel}
        onNameChange={setCreateName}
        onParentChange={setCreateParentId}
        onIsActiveChange={setCreateIsActive}
        onClose={() => {
          if (isCreating) {
            return;
          }
          setCreateModalOpen(false);
          setCreateName("");
          setCreateParentId("");
          setCreateIsActive(true);
        }}
        onSubmit={() => {
          void handleCreateCategory();
        }}
        t={t}
      />

      <CategoryModal
        title={editingCategory ? t("categories.edit.title", { name: getDisplayName(editingCategory) }) : t("categories.edit.fallbackTitle")}
        submitLabel={t("categories.actions.save")}
        isOpen={editModalOpen}
        isSubmitting={isUpdating}
        name={editName}
        parentId={editParentId}
        isActive={editIsActive}
        parentOptions={sortedParentOptions}
        disabledParentIds={disabledParentIds}
        getParentOptionLabel={getParentOptionLabel}
        onNameChange={setEditName}
        onParentChange={setEditParentId}
        onIsActiveChange={setEditIsActive}
        onClose={() => {
          if (isUpdating) {
            return;
          }
          setEditModalOpen(false);
          setEditingCategoryId(null);
          setEditName("");
          setEditParentId("");
          setEditIsActive(true);
        }}
        onSubmit={() => {
          void handleUpdateCategory();
        }}
        t={t}
      />
    </section>
  );
}
