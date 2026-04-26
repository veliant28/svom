"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { requestPasswordReset } from "@/features/auth/api/password-reset";
import { Link } from "@/i18n/navigation";
import type { AppLocale } from "@/i18n/routing";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function ForgotPasswordForm() {
  const t = useTranslations("auth.forgotPassword");
  const locale = useLocale() as AppLocale;
  const { showApiError, showSuccess } = useStorefrontFeedback();
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  return (
    <form
      className="grid gap-3"
      onSubmit={async (event) => {
        event.preventDefault();
        setIsSubmitting(true);
        try {
          await requestPasswordReset({
            email: email.trim(),
            locale,
          });
          showSuccess(t("messages.sent"));
        } catch (error) {
          showApiError(error, t("errors.failed"));
        } finally {
          setIsSubmitting(false);
        }
      }}
    >
      <label className="flex flex-col gap-1 text-xs">
        {t("fields.email")}
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          className="h-10 rounded-md border px-3"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
      </label>

      <button
        type="submit"
        disabled={isSubmitting}
        className="h-10 rounded-md border px-3 text-sm font-semibold disabled:opacity-60"
        style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
      >
        {isSubmitting ? t("actions.submitting") : t("actions.submit")}
      </button>

      <Link href="/login" className="text-xs font-semibold underline underline-offset-2">
        {t("backToLogin")}
      </Link>
    </form>
  );
}
