"use client";

import { useCallback, useMemo, useState } from "react";
import { CheckCircle2, Eye, EyeOff, Pencil, UserCheck, UserX, XCircle, type LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  activateBackofficeUser,
  createBackofficeUser,
  deactivateBackofficeUser,
  getBackofficeRbacMeta,
  listBackofficeGroups,
  listBackofficeUsers,
  updateBackofficeUser,
} from "@/features/backoffice/api/rbac-api";
import { RoleGroupBadge } from "@/features/backoffice/components/rbac/role-group-badge";
import { BackofficeTable } from "@/features/backoffice/components/table/backoffice-table";
import { ActionIconButton } from "@/features/backoffice/components/widgets/action-icon-button";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { canEditBackofficeUserCard } from "@/features/backoffice/lib/capabilities";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type { BackofficeManagedUser, BackofficeManagedUserWritePayload } from "@/features/backoffice/types/rbac.types";
import { PHONE_INPUT_MAX_LENGTH, PHONE_INPUT_PLACEHOLDER, formatPhoneInput } from "@/shared/lib/phone-input";

const EMPTY_FORM: BackofficeManagedUserWritePayload = {
  email: "",
  username: "",
  last_name: "",
  middle_name: "",
  phone: "",
  preferred_language: "uk",
  is_active: true,
  password: "",
  group_ids: [],
  system_role: null,
};

function StatusIconChip({
  label,
  tone,
  icon,
}: {
  label: string;
  tone: "success" | "gray";
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

export function UsersPage() {
  const t = useTranslations("backoffice.common");
  const { user } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const canManageUsers = canEditBackofficeUserCard(user);
  const currentRole = user?.system_role ?? null;
  const isAdministratorRole = currentRole === "administrator";
  const isManagerRole = currentRole === "manager";

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [page, setPage] = useState(1);
  const [editingUser, setEditingUser] = useState<BackofficeManagedUser | null>(null);
  const [isCreateMode, setIsCreateMode] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showManagerPassword, setShowManagerPassword] = useState(false);
  const [form, setForm] = useState<BackofficeManagedUserWritePayload>(EMPTY_FORM);

  const usersQuery = useCallback(
    (token: string) =>
      listBackofficeUsers(token, {
        q: query,
        is_active: statusFilter,
        system_role: roleFilter,
        page,
      }),
    [page, query, roleFilter, statusFilter],
  );

  const usersState = useBackofficeQuery(usersQuery, [query, statusFilter, roleFilter, page]);

  const groupsQuery = useCallback((token: string) => listBackofficeGroups(token, { page: 1 }), []);
  const metaQuery = useCallback((token: string) => getBackofficeRbacMeta(token), []);

  const groupsState = useBackofficeQuery(groupsQuery, []);
  const metaState = useBackofficeQuery(metaQuery, []);

  const users = useMemo(() => normalizeListPayload<BackofficeManagedUser>(usersState.data).results, [usersState.data]);
  const usersCount = useMemo(() => normalizeListPayload<BackofficeManagedUser>(usersState.data).count, [usersState.data]);
  const pagesCount = Math.max(1, Math.ceil(usersCount / 20));

  const groups = useMemo(
    () =>
      normalizeListPayload<{ id: number; name: string }>(groupsState.data).results.filter(
        (group) => !group.name.startsWith("Backoffice Role:"),
      ),
    [groupsState.data],
  );
  const roleOptions = metaState.data?.roles ?? [];

  const selectedRole = useMemo(
    () => roleOptions.find((item) => item.code === (form.system_role ?? "")) ?? null,
    [form.system_role, roleOptions],
  );

  const openCreate = useCallback(() => {
    setIsCreateMode(true);
    setEditingUser(null);
    setShowManagerPassword(false);
    setForm({ ...EMPTY_FORM });
  }, []);

  const openEdit = useCallback(
    (target: BackofficeManagedUser) => {
      setIsCreateMode(false);
      setEditingUser(target);
      setShowManagerPassword(false);
      setForm({
        email: target.email,
        username: target.username,
        last_name: target.last_name,
        middle_name: target.middle_name || "",
        phone: formatPhoneInput(target.phone || ""),
        preferred_language: target.preferred_language,
        is_active: target.is_active,
        password: "",
        group_ids: target.groups.map((group) => group.id),
        system_role: target.system_role,
      });
    },
    [],
  );

  const closeEditor = useCallback(() => {
    setIsCreateMode(false);
    setEditingUser(null);
    setShowManagerPassword(false);
    setForm({ ...EMPTY_FORM });
  }, []);

  const passwordInputType = isAdministratorRole ? "text" : isManagerRole && showManagerPassword ? "text" : "password";

  const submit = useCallback(async () => {
    if (!usersState.token || isSaving || !canManageUsers) {
      return;
    }

    setIsSaving(true);
    try {
      const payload: BackofficeManagedUserWritePayload = {
        ...form,
        email: (form.email || "").trim(),
        username: form.username || "",
        last_name: form.last_name || "",
        middle_name: form.middle_name || "",
        phone: form.phone || "",
        password: form.password || undefined,
      };

      if (isCreateMode) {
        if (!payload.password) {
          showApiError(new Error("Password is required."), t("rbac.users.messages.saveFailed"));
          return;
        }
        await createBackofficeUser(usersState.token, payload);
        showSuccess(t("rbac.users.messages.created"));
      } else if (editingUser) {
        await updateBackofficeUser(usersState.token, editingUser.id, payload);
        showSuccess(t("rbac.users.messages.updated"));
      }

      closeEditor();
      await usersState.refetch();
    } catch (error) {
      showApiError(error, t("rbac.users.messages.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  }, [canManageUsers, closeEditor, editingUser, form, isCreateMode, isSaving, showApiError, showSuccess, t, usersState]);

  const toggleActive = useCallback(
    async (target: BackofficeManagedUser) => {
      if (!usersState.token || !canManageUsers) {
        return;
      }
      try {
        if (target.is_active) {
          await deactivateBackofficeUser(usersState.token, target.id);
          showSuccess(t("rbac.users.messages.deactivated"));
        } else {
          await activateBackofficeUser(usersState.token, target.id);
          showSuccess(t("rbac.users.messages.activated"));
        }
        await usersState.refetch();
      } catch (error) {
        showApiError(error, t("rbac.users.messages.toggleFailed"));
      }
    },
    [canManageUsers, showApiError, showSuccess, t, usersState],
  );

  const asyncError = usersState.error || metaState.error || groupsState.error;

  return (
    <AsyncState
      isLoading={usersState.isLoading || metaState.isLoading || groupsState.isLoading}
      error={asyncError}
      empty={false}
      emptyLabel=""
    >
      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
      <div>
        <PageHeader title={t("rbac.users.title")} description={t("rbac.users.subtitle")} />

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder={t("rbac.users.filters.search")}
            className="h-9 min-w-[240px] rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(1);
            }}
            className="h-9 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">{t("rbac.users.filters.allStatuses")}</option>
            <option value="true">{t("statuses.active")}</option>
            <option value="false">{t("statuses.inactive")}</option>
          </select>
          <select
            value={roleFilter}
            onChange={(event) => {
              setRoleFilter(event.target.value);
              setPage(1);
            }}
            className="h-9 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <option value="">{t("rbac.users.filters.allRoles")}</option>
            {roleOptions.map((role) => (
              <option key={role.code} value={role.code}>{t(`rbac.roles.values.${role.code}`)}</option>
            ))}
          </select>
          {canManageUsers ? (
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              onClick={openCreate}
            >
              {t("rbac.users.actions.create")}
            </button>
          ) : null}
        </div>

        <BackofficeTable
          columns={[
            { key: "email", label: t("rbac.users.columns.email"), render: (item) => <div><p className="font-semibold">{item.email}</p><p className="text-xs" style={{ color: "var(--muted)" }}>{item.full_name}</p></div> },
            { key: "role", label: t("rbac.users.columns.role"), render: (item) => (item.system_role ? t("yes") : t("no")) },
            {
              key: "groups",
              label: t("rbac.users.columns.groups"),
              render: (item) =>
                item.groups.length ? (
                  <div className="flex flex-wrap gap-1">
                    {item.groups.map((group) => (
                      <RoleGroupBadge key={`${item.id}-${group.id}`} groupName={group.name} />
                    ))}
                  </div>
                ) : (
                  "-"
                ),
            },
            {
              key: "status",
              label: t("rbac.users.columns.status"),
              render: (item) => (
                <StatusIconChip
                  label={item.is_active ? t("statuses.active") : t("statuses.inactive")}
                  tone={item.is_active ? "success" : "gray"}
                  icon={item.is_active ? CheckCircle2 : XCircle}
                />
              ),
            },
            {
              key: "actions",
              label: t("rbac.users.columns.actions"),
              render: (item) => (
                <div className="flex gap-2">
                  <ActionIconButton
                    label={t("rbac.users.actions.edit")}
                    icon={Pencil}
                    onClick={() => openEdit(item)}
                  />
                  {canManageUsers ? (
                    <ActionIconButton
                      label={item.is_active ? t("rbac.users.actions.deactivate") : t("rbac.users.actions.activate")}
                      icon={item.is_active ? UserX : UserCheck}
                      tone={item.is_active ? "danger" : "default"}
                      onClick={() => {
                        void toggleActive(item);
                      }}
                    />
                  ) : null}
                </div>
              ),
            },
          ]}
          rows={users}
          emptyLabel={t("rbac.users.empty")}
        />

        <div className="mt-2 flex items-center gap-2 text-xs" style={{ color: "var(--muted)" }}>
          <span>{t("rbac.users.pagination", { page, pages: pagesCount })}</span>
          <button type="button" className="h-8 rounded-md border px-2" style={{ borderColor: "var(--border)" }} disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>◀</button>
          <button type="button" className="h-8 rounded-md border px-2" style={{ borderColor: "var(--border)" }} disabled={page >= pagesCount} onClick={() => setPage((prev) => Math.min(pagesCount, prev + 1))}>▶</button>
        </div>
      </div>

      <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-sm font-semibold">{isCreateMode ? t("rbac.users.editor.createTitle") : t("rbac.users.editor.editTitle")}</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("rbac.users.editor.helper")}</p>

        <div className="mt-3 grid gap-2">
          <input value={form.email || ""} onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))} placeholder={t("rbac.users.fields.email")} className="h-9 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} disabled={!canManageUsers} />
          <input value={form.username || ""} onChange={(event) => setForm((prev) => ({ ...prev, username: event.target.value }))} placeholder={t("rbac.users.fields.username")} className="h-9 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} disabled={!canManageUsers} />
          <input value={form.last_name || ""} onChange={(event) => setForm((prev) => ({ ...prev, last_name: event.target.value }))} placeholder={t("rbac.users.fields.lastName")} className="h-9 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} disabled={!canManageUsers} />
          <input
            value={form.phone || ""}
            onChange={(event) => setForm((prev) => ({ ...prev, phone: formatPhoneInput(event.target.value) }))}
            placeholder={PHONE_INPUT_PLACEHOLDER}
            inputMode="numeric"
            maxLength={PHONE_INPUT_MAX_LENGTH}
            title={PHONE_INPUT_PLACEHOLDER}
            className="h-9 rounded-md border px-3 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            disabled={!canManageUsers}
          />
          <div className="relative">
            <input
              type={passwordInputType}
              value={form.password || ""}
              onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
              placeholder={t("rbac.users.fields.password")}
              className="h-9 w-full rounded-md border px-3 pr-10 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              disabled={!canManageUsers}
            />
            {isManagerRole ? (
              <button
                type="button"
                aria-label={showManagerPassword ? t("rbac.users.actions.hidePassword") : t("rbac.users.actions.showPassword")}
                title={showManagerPassword ? t("rbac.users.actions.hidePassword") : t("rbac.users.actions.showPassword")}
                onClick={() => setShowManagerPassword((value) => !value)}
                className="absolute inset-y-0 right-0 inline-flex w-10 items-center justify-center"
                style={{ color: "var(--muted)" }}
              >
                {showManagerPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            ) : null}
          </div>

          <select value={form.system_role || ""} onChange={(event) => setForm((prev) => ({ ...prev, system_role: (event.target.value || null) as BackofficeManagedUserWritePayload["system_role"] }))} className="h-9 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} disabled={!canManageUsers}>
            <option value="">{t("rbac.users.fields.noRole")}</option>
            {roleOptions.map((role) => (
              <option key={role.code} value={role.code}>{t(`rbac.roles.values.${role.code}`)}</option>
            ))}
          </select>

          <label className="inline-flex items-center gap-2 text-xs">
            <input type="checkbox" checked={Boolean(form.is_active)} onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))} disabled={!canManageUsers} />
            {t("rbac.users.fields.active")}
          </label>

          <div className="rounded-md border p-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="font-semibold">{t("rbac.users.fields.groups")}</p>
            <div className="mt-1 grid gap-1">
              {groups.map((group) => {
                const checked = (form.group_ids || []).includes(group.id);
                return (
                  <label key={group.id} className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={!canManageUsers}
                      onChange={(event) => {
                        setForm((prev) => {
                          const previous = new Set(prev.group_ids || []);
                          if (event.target.checked) {
                            previous.add(group.id);
                          } else {
                            previous.delete(group.id);
                          }
                          return { ...prev, group_ids: Array.from(previous) };
                        });
                      }}
                    />
                    {group.name}
                  </label>
                );
              })}
            </div>
          </div>

          <div className="rounded-md border p-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="font-semibold">{t("rbac.users.rolePreview.title")}</p>
            <p style={{ color: "var(--muted)" }}>{selectedRole ? t(`rbac.roles.descriptions.${selectedRole.code}`) : t("rbac.users.rolePreview.none")}</p>
          </div>
          <div className="rounded-md border p-2 text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="font-semibold">{t("rbac.users.fields.backofficeAccess")}</p>
            <p style={{ color: "var(--muted)" }}>
              {editingUser?.has_backoffice_access ? t("yes") : t("no")}
            </p>
          </div>

          <div className="flex gap-2">
            <button type="button" className="h-9 rounded-md border px-3 text-xs font-semibold" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} onClick={() => { void submit(); }} disabled={!canManageUsers || isSaving}>
              {isSaving ? t("rbac.users.actions.saving") : t("rbac.users.actions.save")}
            </button>
            <button type="button" className="h-9 rounded-md border px-3 text-xs font-semibold" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} onClick={closeEditor}>
              {t("rbac.users.actions.reset")}
            </button>
          </div>
        </div>
      </div>
      </section>
    </AsyncState>
  );
}
