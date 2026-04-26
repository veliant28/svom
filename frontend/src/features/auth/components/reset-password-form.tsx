"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { confirmPasswordReset } from "@/features/auth/api/password-reset";
import { Link, useRouter } from "@/i18n/navigation";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function ResetPasswordForm({
  uid,
  token,
}: {
  uid: string;
  token: string;
}) {
  const t = useTranslations("auth.resetPassword");
  const router = useRouter();
  const { showApiError, showError, showSuccess } = useStorefrontFeedback();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  return (
    <form
      className="grid gap-3"
      onSubmit={async (event) => {
        event.preventDefault();
        if (password !== confirmPassword) {
          showError(t("errors.passwordMismatch"));
          return;
        }

        setIsSubmitting(true);
        try {
          await confirmPasswordReset({
            uid,
            token,
            new_password: password,
          });
          showSuccess(t("messages.updated"));
          router.push("/login");
        } catch (error) {
          showApiError(error, t("errors.failed"));
        } finally {
          setIsSubmitting(false);
        }
      }}
    >
      <label className="flex flex-col gap-1 text-xs">
        {t("fields.password")}
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          minLength={8}
          className="h-10 rounded-md border px-3"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
      </label>

      <label className="flex flex-col gap-1 text-xs">
        {t("fields.confirmPassword")}
        <input
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          required
          minLength={8}
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
