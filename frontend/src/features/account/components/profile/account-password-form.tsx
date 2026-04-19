"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type AccountPasswordFormProps = {
  isSubmitting: boolean;
  onSubmit: (payload: { current_password: string; new_password: string }) => Promise<void>;
};

const EXACT_PASSWORD_LENGTH = 8;

export function AccountPasswordForm({
  isSubmitting,
  onSubmit,
}: AccountPasswordFormProps) {
  const t = useTranslations("auth.profile");
  const { showError } = useStorefrontFeedback();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  return (
    <form
      className="rounded-xl border p-4"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      onSubmit={async (event) => {
        event.preventDefault();

        if (newPassword !== confirmPassword) {
          showError(t("errors.passwordMismatch"));
          return;
        }
        if (newPassword.length !== EXACT_PASSWORD_LENGTH) {
          showError(t("errors.passwordLengthExact"));
          return;
        }

        await onSubmit({
          current_password: currentPassword,
          new_password: newPassword,
        });
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      }}
    >
      <h2 className="text-lg font-semibold">{t("sections.password")}</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs sm:col-span-2">
          {t("fields.currentPassword")}
          <input
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.newPassword")}
          <input
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value.slice(0, EXACT_PASSWORD_LENGTH))}
            required
            minLength={EXACT_PASSWORD_LENGTH}
            maxLength={EXACT_PASSWORD_LENGTH}
            title={t("errors.passwordLengthExact")}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.confirmPassword")}
          <input
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value.slice(0, EXACT_PASSWORD_LENGTH))}
            required
            minLength={EXACT_PASSWORD_LENGTH}
            maxLength={EXACT_PASSWORD_LENGTH}
            title={t("errors.passwordLengthExact")}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />
        </label>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-4 inline-flex h-10 items-center rounded-lg border px-4 text-sm font-medium disabled:opacity-60"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        {isSubmitting ? t("actions.updatingPassword") : t("actions.updatePassword")}
      </button>
    </form>
  );
}
