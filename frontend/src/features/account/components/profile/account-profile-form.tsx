"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Globe } from "lucide-react";
import { useTranslations } from "next-intl";

import { RoleGroupBadge } from "@/features/backoffice/components/rbac/role-group-badge";
import type { AuthUser } from "@/features/auth/types/auth";
import {
  PHONE_INPUT_MAX_LENGTH,
  PHONE_INPUT_PLACEHOLDER,
  PHONE_INPUT_REGEX,
  formatPhoneInput,
  isPhoneInputValid,
} from "@/shared/lib/phone-input";

export type AccountProfileFormValues = Pick<
  AuthUser,
  "email" | "username" | "last_name" | "middle_name" | "phone" | "preferred_language"
>;

type AccountProfileFormProps = {
  user: AuthUser;
  isSubmitting: boolean;
  onSubmit: (values: AccountProfileFormValues) => Promise<void>;
};

const localeOptions: Array<AuthUser["preferred_language"]> = ["uk", "ru", "en"];

function mapUserToForm(user: AuthUser): AccountProfileFormValues {
  return {
    email: user.email,
    username: user.username || "",
    last_name: user.last_name || "",
    middle_name: user.middle_name || "",
    phone: formatPhoneInput(user.phone || ""),
    preferred_language: user.preferred_language,
  };
}

export function AccountProfileForm({
  user,
  isSubmitting,
  onSubmit,
}: AccountProfileFormProps) {
  const t = useTranslations("auth.profile");
  const tHeader = useTranslations("common.header");
  const [values, setValues] = useState<AccountProfileFormValues>(() => mapUserToForm(user));
  const [isLanguageOpen, setIsLanguageOpen] = useState(false);
  const languageWrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setValues(mapUserToForm(user));
  }, [user]);

  useEffect(() => {
    if (!isLanguageOpen) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      if (!languageWrapperRef.current?.contains(event.target as Node)) {
        setIsLanguageOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsLanguageOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isLanguageOpen]);

  const canSubmit = useMemo(() => {
    return (
      values.email.trim().length > 0 &&
      values.username.trim().length > 0 &&
      isPhoneInputValid(values.phone) &&
      values.preferred_language.length > 0
    );
  }, [values.email, values.phone, values.preferred_language, values.username]);
  const profileGroupName = useMemo(() => {
    if (user.system_role) {
      return `Backoffice Role: ${user.system_role}`;
    }
    return user.groups[0]?.name || "";
  }, [user.groups, user.system_role]);

  return (
    <form
      className="rounded-xl border p-4"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      onSubmit={async (event) => {
        event.preventDefault();
        await onSubmit(values);
      }}
    >
      <h2 className="text-lg font-semibold">{t("sections.base")}</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1 text-xs">
          <span className="h-[14px]" aria-hidden />
          <div className="inline-flex h-10 items-center justify-center">
            {profileGroupName ? <RoleGroupBadge groupName={profileGroupName} /> : <span style={{ color: "var(--muted)" }}>-</span>}
          </div>
        </div>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.email")}
          <input
            type="email"
            value={values.email}
            onChange={(event) => setValues((current) => ({ ...current, email: event.target.value }))}
            required
            className="h-10 w-full rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.username")}
          <input
            value={values.username}
            onChange={(event) => setValues((current) => ({ ...current, username: event.target.value }))}
            required
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.lastName")}
          <input
            value={values.last_name}
            onChange={(event) => setValues((current) => ({ ...current, last_name: event.target.value }))}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.phone")}
          <input
            value={values.phone}
            onChange={(event) => setValues((current) => ({ ...current, phone: formatPhoneInput(event.target.value) }))}
            placeholder={PHONE_INPUT_PLACEHOLDER}
            inputMode="numeric"
            required
            pattern={PHONE_INPUT_REGEX.source}
            maxLength={PHONE_INPUT_MAX_LENGTH}
            title={PHONE_INPUT_PLACEHOLDER}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.middleName")}
          <input
            value={values.middle_name}
            onChange={(event) => setValues((current) => ({ ...current, middle_name: event.target.value }))}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <button
          type="submit"
          disabled={isSubmitting || !canSubmit}
          className="inline-flex h-10 items-center rounded-lg border px-4 text-sm font-medium disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          {isSubmitting ? t("actions.saving") : t("actions.save")}
        </button>

        <div ref={languageWrapperRef} className="relative inline-flex">
          <span className="group relative inline-flex">
            <button
              type="button"
              className="header-control header-control-wide min-w-[4.5rem] gap-1.5"
              aria-label={tHeader("tooltips.language")}
              aria-haspopup="menu"
              aria-expanded={isLanguageOpen ? "true" : "false"}
              onClick={() => setIsLanguageOpen((previous) => !previous)}
              style={{ borderRadius: "0.5rem" }}
            >
              <Globe size={18} />
              <span className="text-sm font-semibold leading-none tracking-[0.06em]">
                {values.preferred_language.toUpperCase()}
              </span>
            </button>
            <span role="tooltip" className="header-tooltip hidden group-hover:block">
              {tHeader("tooltips.language")}
            </span>
          </span>

          {isLanguageOpen ? (
            <div
              className="header-dropdown min-w-[10rem]"
              role="menu"
              aria-label={tHeader("tooltips.language")}
              style={{ borderRadius: "0.5rem" }}
            >
              {localeOptions.map((item) => (
                <button
                  key={item}
                  type="button"
                  className="header-menu-item justify-between"
                  role="menuitemradio"
                  aria-checked={values.preferred_language === item}
                  onClick={() => {
                    setValues((current) => ({ ...current, preferred_language: item }));
                    setIsLanguageOpen(false);
                  }}
                >
                  <span>{tHeader(`languages.${item}`)}</span>
                  <span
                    className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                    style={{
                      backgroundColor: values.preferred_language === item ? "color-mix(in srgb, var(--accent) 24%, transparent)" : "transparent",
                      color: "var(--text)",
                    }}
                  >
                    {item.toUpperCase()}
                  </span>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </form>
  );
}
