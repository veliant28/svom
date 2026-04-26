"use client";

import { useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { Link, useRouter } from "@/i18n/navigation";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";
import {
  PHONE_INPUT_MAX_LENGTH,
  PHONE_INPUT_PLACEHOLDER,
  PHONE_INPUT_REGEX,
  formatPhoneInput,
  isPhoneInputValid,
} from "@/shared/lib/phone-input";
import type { AppLocale } from "@/i18n/routing";

export function RegisterForm() {
  const t = useTranslations("auth.register");
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const { register, isAuthenticated } = useAuth();
  const { showApiError, showError, showSuccess } = useStorefrontFeedback();
  const [values, setValues] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    firstName: "",
    lastName: "",
    phone: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit = useMemo(() => {
    return (
      values.email.trim().length > 0
      && values.password.length >= 8
      && values.confirmPassword.length >= 8
      && values.firstName.trim().length > 0
      && isPhoneInputValid(values.phone)
    );
  }, [values]);

  if (isAuthenticated) {
    return (
      <p className="text-sm" style={{ color: "var(--success, #136f3a)" }}>
        {t("alreadyLoggedIn")}
      </p>
    );
  }

  return (
    <form
      className="grid gap-3"
      onSubmit={async (event) => {
        event.preventDefault();
        if (values.password !== values.confirmPassword) {
          showError(t("errors.passwordMismatch"));
          return;
        }
        if (values.password.length < 8) {
          showError(t("errors.passwordLength"));
          return;
        }
        if (!isPhoneInputValid(values.phone)) {
          showError(t("errors.phoneFormat"));
          return;
        }

        setIsSubmitting(true);
        try {
          await register({
            email: values.email.trim(),
            password: values.password,
            first_name: values.firstName.trim(),
            last_name: values.lastName.trim(),
            phone: values.phone,
            preferred_language: locale,
          });
          showSuccess(t("messages.created"));
          router.push("/account/profile");
        } catch (error) {
          showApiError(error, t("errors.failed"));
        } finally {
          setIsSubmitting(false);
        }
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.email")}
          <input
            type="email"
            value={values.email}
            onChange={(event) => setValues((current) => ({ ...current, email: event.target.value }))}
            required
            autoComplete="email"
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
            autoComplete="tel"
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.firstName")}
          <input
            value={values.firstName}
            onChange={(event) => setValues((current) => ({ ...current, firstName: event.target.value }))}
            required
            autoComplete="given-name"
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.lastName")}
          <input
            value={values.lastName}
            onChange={(event) => setValues((current) => ({ ...current, lastName: event.target.value }))}
            autoComplete="family-name"
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.password")}
          <input
            type="password"
            value={values.password}
            onChange={(event) => setValues((current) => ({ ...current, password: event.target.value }))}
            required
            minLength={8}
            title={t("errors.passwordLength")}
            autoComplete="new-password"
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.confirmPassword")}
          <input
            type="password"
            value={values.confirmPassword}
            onChange={(event) => setValues((current) => ({ ...current, confirmPassword: event.target.value }))}
            required
            minLength={8}
            title={t("errors.passwordLength")}
            autoComplete="new-password"
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
      </div>

      <button
        type="submit"
        disabled={isSubmitting || !canSubmit}
        className="h-10 rounded-md border px-3 text-sm font-semibold disabled:opacity-60"
        style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
      >
        {isSubmitting ? t("actions.submitting") : t("actions.submit")}
      </button>

      <p className="text-xs" style={{ color: "var(--muted)" }}>
        {t("loginHint")}{" "}
        <Link href="/login" className="font-semibold underline underline-offset-2">
          {t("loginAction")}
        </Link>
      </p>
    </form>
  );
}
