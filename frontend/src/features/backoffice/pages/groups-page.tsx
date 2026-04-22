"use client";

import { useCallback, useMemo, useState } from "react";
import { Check, Pencil } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  createBackofficeGroup,
  getBackofficeRbacMeta,
  listBackofficeGroups,
  updateBackofficeGroup,
} from "@/features/backoffice/api/rbac-api";
import { RoleGroupBadge } from "@/features/backoffice/components/rbac/role-group-badge";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { BACKOFFICE_CAPABILITIES, hasBackofficeCapability } from "@/features/backoffice/lib/capabilities";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeGroupItem, BackofficeGroupWritePayload } from "@/features/backoffice/types/rbac.types";
import type { BackofficeCapabilityCode } from "@/features/backoffice/types/shared.types";

const USERS_MANAGEMENT_BUNDLE_CODE = "users.management.bundle";
const BACKOFFICE_ACCESS_CODE = "backoffice.access";
const VIEW_SUFFIX = ".view";
const MANAGE_SUFFIX = ".manage";
const USERS_MANAGEMENT_CAPABILITY_CODES: BackofficeCapabilityCode[] = [
  "users.manage",
  "users.card.edit.administrator",
  "users.card.edit.manager",
  "users.card.edit.all",
];

type GroupEditorForm = {
  name: string;
  capability_codes: string[];
};

const EMPTY_FORM: GroupEditorForm = {
  name: "",
  capability_codes: [],
};

function hasUsersManagementCapability(codes: string[]): boolean {
  return codes.some((code) => USERS_MANAGEMENT_CAPABILITY_CODES.includes(code as BackofficeCapabilityCode));
}

function collapseUsersManagementCapabilities(codes: string[]): string[] {
  const next = codes.filter((code) => !USERS_MANAGEMENT_CAPABILITY_CODES.includes(code as BackofficeCapabilityCode));
  if (!hasUsersManagementCapability(codes)) {
    return Array.from(new Set(next));
  }

  const usersViewIndex = next.findIndex((code) => code === "users.view");
  if (usersViewIndex < 0) {
    next.unshift(USERS_MANAGEMENT_BUNDLE_CODE);
  } else {
    next.splice(usersViewIndex + 1, 0, USERS_MANAGEMENT_BUNDLE_CODE);
  }

  return Array.from(new Set(next));
}

function expandUsersManagementCapabilities(codes: string[]): BackofficeCapabilityCode[] {
  const next = new Set<BackofficeCapabilityCode>();
  for (const code of codes) {
    if (code === USERS_MANAGEMENT_BUNDLE_CODE) {
      next.add("users.manage");
      next.add("users.card.edit.all");
      continue;
    }
    next.add(code as BackofficeCapabilityCode);
  }
  return Array.from(next);
}

function normalizeListPayload<T>(payload: unknown): { count: number; results: T[] } {
  if (payload && typeof payload === "object" && "results" in payload) {
    const typed = payload as { count?: number; results?: T[] };
    return {
      count: Number(typed.count || 0),
      results: Array.isArray(typed.results) ? typed.results : [],
    };
  }
  return { count: 0, results: [] };
}

export function GroupsPage() {
  const t = useTranslations("backoffice.common");
  const { user } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const canManageGroups = hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.groupsManage);
  const isAdministratorRole = user?.system_role === "administrator";
  const canCreateGroups = canManageGroups && isAdministratorRole;

  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [editingGroup, setEditingGroup] = useState<BackofficeGroupItem | null>(null);
  const [isCreateMode, setIsCreateMode] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState<GroupEditorForm>(EMPTY_FORM);

  const groupsQuery = useCallback((token: string) => listBackofficeGroups(token, { q: query, page }), [page, query]);
  const groupsState = useBackofficeQuery(groupsQuery, [query, page]);
  const metaQuery = useCallback((token: string) => getBackofficeRbacMeta(token), []);
  const metaState = useBackofficeQuery(metaQuery, []);

  const groups = useMemo(() => normalizeListPayload<BackofficeGroupItem>(groupsState.data).results, [groupsState.data]);
  const groupsCount = useMemo(() => normalizeListPayload<BackofficeGroupItem>(groupsState.data).count, [groupsState.data]);
  const pagesCount = Math.max(1, Math.ceil(groupsCount / 20));

  const capabilities = metaState.data?.capabilities ?? [];
  const collator = useMemo(() => new Intl.Collator(undefined, { sensitivity: "base" }), []);
  const capabilitiesByCode = useMemo(
    () => new Map(capabilities.map((capability) => [capability.code, capability])),
    [capabilities],
  );

  const getCapabilityTitle = useCallback((code: string, fallback?: string) => {
    if (code === USERS_MANAGEMENT_BUNDLE_CODE) {
      return fallback || t("rbac.groups.capabilityBundles.usersManagement.title");
    }
    try {
      return t(`rbac.capabilities.${code}.title` as never);
    } catch {
      return fallback || code;
    }
  }, [t]);

  const getCapabilityDescription = useCallback((code: string, fallback?: string) => {
    if (code === USERS_MANAGEMENT_BUNDLE_CODE) {
      return fallback || t("rbac.groups.capabilityBundles.usersManagement.description");
    }
    try {
      return t(`rbac.capabilities.${code}.description` as never);
    } catch {
      return fallback || "";
    }
  }, [t]);

  const sortCapabilityCodes = useCallback((codes: string[]) => {
    const codesSet = new Set(codes);
    const getPairedBase = (code: string): string | null => {
      if (code.endsWith(VIEW_SUFFIX)) {
        return code.slice(0, -VIEW_SUFFIX.length);
      }
      if (code.endsWith(MANAGE_SUFFIX)) {
        return code.slice(0, -MANAGE_SUFFIX.length);
      }
      return null;
    };
    const getGroupTitle = (code: string): string => {
      const base = getPairedBase(code);
      if (!base) {
        return getCapabilityTitle(code, capabilitiesByCode.get(code as BackofficeCapabilityCode)?.title);
      }
      const viewCode = `${base}${VIEW_SUFFIX}`;
      if (codesSet.has(viewCode)) {
        return getCapabilityTitle(viewCode, capabilitiesByCode.get(viewCode as BackofficeCapabilityCode)?.title);
      }
      return getCapabilityTitle(code, capabilitiesByCode.get(code as BackofficeCapabilityCode)?.title);
    };
    const getWithinGroupRank = (code: string): number => {
      if (code.endsWith(VIEW_SUFFIX)) {
        return 0;
      }
      if (code.endsWith(MANAGE_SUFFIX)) {
        return 1;
      }
      return 0;
    };

    return [...codes].sort((leftCode, rightCode) => {
      if (leftCode === BACKOFFICE_ACCESS_CODE && rightCode !== BACKOFFICE_ACCESS_CODE) {
        return -1;
      }
      if (rightCode === BACKOFFICE_ACCESS_CODE && leftCode !== BACKOFFICE_ACCESS_CODE) {
        return 1;
      }

      const leftGroupTitle = getGroupTitle(leftCode);
      const rightGroupTitle = getGroupTitle(rightCode);
      const byGroup = collator.compare(leftGroupTitle, rightGroupTitle);
      if (byGroup !== 0) {
        return byGroup;
      }

      const leftBase = getPairedBase(leftCode);
      const rightBase = getPairedBase(rightCode);
      if (leftBase && rightBase && leftBase === rightBase) {
        const byRank = getWithinGroupRank(leftCode) - getWithinGroupRank(rightCode);
        if (byRank !== 0) {
          return byRank;
        }
      }

      const leftTitle = getCapabilityTitle(leftCode, capabilitiesByCode.get(leftCode as BackofficeCapabilityCode)?.title);
      const rightTitle = getCapabilityTitle(rightCode, capabilitiesByCode.get(rightCode as BackofficeCapabilityCode)?.title);
      return collator.compare(leftTitle, rightTitle);
    });
  }, [capabilitiesByCode, collator, getCapabilityTitle]);

  const displayCapabilities = useMemo(() => {
    const visible = capabilities
      .filter((capability) => !USERS_MANAGEMENT_CAPABILITY_CODES.includes(capability.code))
      .map((capability) => ({
        code: String(capability.code),
        title: capability.title,
        description: capability.description,
      }));
    const usersManagementBundle = {
      code: USERS_MANAGEMENT_BUNDLE_CODE,
      title: t("rbac.groups.capabilityBundles.usersManagement.title"),
      description: t("rbac.groups.capabilityBundles.usersManagement.description"),
    };
    return sortCapabilityCodes([usersManagementBundle.code, ...visible.map((item) => item.code)])
      .map((code) => {
        if (code === USERS_MANAGEMENT_BUNDLE_CODE) {
          return usersManagementBundle;
        }
        const capability = visible.find((item) => item.code === code);
        return capability || {
          code,
          title: capabilitiesByCode.get(code as BackofficeCapabilityCode)?.title || code,
          description: capabilitiesByCode.get(code as BackofficeCapabilityCode)?.description || "",
        };
      });
  }, [capabilities, capabilitiesByCode, sortCapabilityCodes, t]);

  const openCreate = useCallback(() => {
    if (!canCreateGroups) {
      return;
    }
    setIsCreateMode(true);
    setEditingGroup(null);
    setForm({ ...EMPTY_FORM });
  }, [canCreateGroups]);

  const openEdit = useCallback((target: BackofficeGroupItem) => {
    setIsCreateMode(false);
    setEditingGroup(target);
    setForm({
      name: target.name,
      capability_codes: collapseUsersManagementCapabilities(target.capability_codes),
    });
  }, []);

  const closeEditor = useCallback(() => {
    setIsCreateMode(false);
    setEditingGroup(null);
    setForm({ ...EMPTY_FORM });
  }, []);

  const submit = useCallback(async () => {
    if (!groupsState.token || isSaving || !canManageGroups) {
      return;
    }
    if (isCreateMode && !canCreateGroups) {
      return;
    }

    setIsSaving(true);
    try {
      const payload: BackofficeGroupWritePayload = {
        name: (form.name || "").trim(),
        capability_codes: expandUsersManagementCapabilities(form.capability_codes || []),
      };

      if (isCreateMode) {
        await createBackofficeGroup(groupsState.token, payload);
        showSuccess(t("rbac.groups.messages.created"));
      } else if (editingGroup) {
        await updateBackofficeGroup(groupsState.token, editingGroup.id, payload);
        showSuccess(t("rbac.groups.messages.updated"));
      }

      closeEditor();
      await groupsState.refetch();
    } catch (error) {
      showApiError(error, t("rbac.groups.messages.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }, [canCreateGroups, canManageGroups, closeEditor, editingGroup, form, groupsState, isCreateMode, isSaving, showApiError, showSuccess, t]);

  const asyncError = groupsState.error || metaState.error;
  const isSystemRoleReadonly = Boolean(editingGroup?.is_system_role_group) && !isAdministratorRole;

  return (
    <AsyncState
      isLoading={groupsState.isLoading || metaState.isLoading}
      error={asyncError}
      empty={false}
      emptyLabel=""
    >
      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
      <div>
        <PageHeader title={t("rbac.groups.title")} description={t("rbac.groups.subtitle")} />

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder={t("rbac.groups.filters.search")}
            className="h-9 min-w-[240px] rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
          {canCreateGroups ? (
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              onClick={openCreate}
            >
              {t("rbac.groups.actions.create")}
            </button>
          ) : null}
        </div>

        <BackofficeTable
          columns={[
            {
              key: "name",
              label: t("rbac.groups.columns.name"),
              render: (item) => (
                <div className="grid gap-1">
                  <RoleGroupBadge groupName={item.name} />
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {item.is_system_role_group ? t("rbac.groups.columns.system") : t("rbac.groups.columns.custom")}
                  </p>
                </div>
              ),
            },
            { key: "members", label: t("rbac.groups.columns.members"), render: (item) => String(item.members_count) },
            {
              key: "capabilities",
              label: t("rbac.groups.columns.capabilities"),
              render: (item) => {
                const collapsed = sortCapabilityCodes(collapseUsersManagementCapabilities(item.capability_codes));
                return collapsed.length
                  ? collapsed
                    .map((code) => {
                      if (code === USERS_MANAGEMENT_BUNDLE_CODE) {
                        return t("rbac.groups.capabilityBundles.usersManagement.title");
                      }
                      return getCapabilityTitle(code, capabilitiesByCode.get(code as BackofficeCapabilityCode)?.title);
                    })
                    .join(", ")
                  : "-";
              },
            },
            {
              key: "actions",
              label: t("rbac.groups.columns.actions"),
              render: (item) => (
                <ActionIconButton
                  label={t("rbac.groups.actions.edit")}
                  icon={Pencil}
                  onClick={() => openEdit(item)}
                />
              ),
            },
          ]}
          rows={groups}
          emptyLabel={t("rbac.groups.empty")}
        />

        <div className="mt-2 flex items-center gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span>{t("rbac.groups.pagination", { page, pages: pagesCount })}</span>
          <button type="button" className="h-8 rounded-md border px-2" style={{ borderColor: "var(--border)" }} disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>◀</button>
          <button type="button" className="h-8 rounded-md border px-2" style={{ borderColor: "var(--border)" }} disabled={page >= pagesCount} onClick={() => setPage((prev) => Math.min(pagesCount, prev + 1))}>▶</button>
        </div>
      </div>

      <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{isCreateMode ? t("rbac.groups.editor.createTitle") : t("rbac.groups.editor.editTitle")}</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("rbac.groups.editor.helper")}</p>

        <div className="mt-3 grid gap-2">
          <input value={form.name || ""} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} placeholder={t("rbac.groups.fields.name")} className="h-9 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} disabled={!canManageGroups || isSystemRoleReadonly} />

          <div className="rounded-md border p-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="font-semibold">{t("rbac.groups.fields.capabilities")}</p>
            <div className="mt-1 grid gap-1">
              {displayCapabilities.map((capability) => {
                const checked = (form.capability_codes || []).includes(capability.code);
                const isReadOnly = !canManageGroups || isSystemRoleReadonly;
                return (
                  <label key={capability.code} className="inline-flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={isReadOnly}
                      className="sr-only"
                      onChange={(event) => {
                        setForm((prev) => {
                          const next = new Set(prev.capability_codes || []);
                          if (event.target.checked) {
                            next.add(capability.code);
                          } else {
                            next.delete(capability.code);
                          }
                          return { ...prev, capability_codes: Array.from(next) };
                        });
                      }}
                    />
                    <span
                      className="mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded border"
                      style={{
                        borderColor: checked ? "#1d4ed8" : "var(--border)",
                        backgroundColor: checked ? "#2563eb" : "var(--surface)",
                        color: "#ffffff",
                        opacity: isReadOnly ? 0.85 : 1,
                      }}
                    >
                      {checked ? <Check className="h-3 w-3" /> : null}
                    </span>
                    <span>
                      <span className="font-semibold">
                        {getCapabilityTitle(capability.code, capability.title)}
                      </span>
                      <span className="block" style={{ color: "var(--muted)" }}>
                        {getCapabilityDescription(capability.code, capability.description)}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          {isSystemRoleReadonly ? (
            <p className="text-xs" style={{ color: "#d97706" }}>{t("rbac.groups.messages.systemReadonly")}</p>
          ) : null}

          <div className="flex gap-2">
            <button type="button" className="h-9 rounded-md border px-3 text-xs font-semibold" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} onClick={() => { void submit(); }} disabled={!canManageGroups || isSaving || isSystemRoleReadonly || (isCreateMode && !canCreateGroups)}>
              {isSaving ? t("rbac.groups.actions.saving") : t("rbac.groups.actions.save")}
            </button>
            <button type="button" className="h-9 rounded-md border px-3 text-xs font-semibold" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} onClick={closeEditor}>
              {t("rbac.groups.actions.reset")}
            </button>
          </div>
        </div>
      </div>
      </section>
    </AsyncState>
  );
}
