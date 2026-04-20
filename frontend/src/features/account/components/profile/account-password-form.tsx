"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useTranslations } from "next-intl";

import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type AccountPasswordFormProps = {
  isSubmitting: boolean;
  onSubmit: (payload: { current_password: string; new_password: string }) => Promise<void>;
};

const MIN_PASSWORD_LENGTH = 8;

export function AccountPasswordForm({
  isSubmitting,
  onSubmit,
}: AccountPasswordFormProps) {
  const t = useTranslations("auth.profile");
  const { showError } = useStorefrontFeedback();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

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
        if (newPassword.length < MIN_PASSWORD_LENGTH) {
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
        setShowCurrentPassword(false);
        setShowNewPassword(false);
        setShowConfirmPassword(false);
      }}
    >
      <h2 className="text-lg font-semibold">{t("sections.password")}</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs sm:col-span-2">
          {t("fields.currentPassword")}
          <div className="relative">
            <input
              type={showCurrentPassword ? "text" : "password"}
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
              className="h-10 w-full rounded-md border px-3 pr-10"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
            <button
              type="button"
              aria-label={showCurrentPassword ? t("actions.hidePassword") : t("actions.showPassword")}
              title={showCurrentPassword ? t("actions.hidePassword") : t("actions.showPassword")}
              onClick={() => setShowCurrentPassword((value) => !value)}
              className="absolute inset-y-0 right-0 inline-flex w-10 items-center justify-center"
              style={{ color: "var(--muted)" }}
            >
              {showCurrentPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.newPassword")}
          <div className="relative">
            <input
              type={showNewPassword ? "text" : "password"}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
              minLength={MIN_PASSWORD_LENGTH}
              title={t("errors.passwordLengthExact")}
              className="h-10 w-full rounded-md border px-3 pr-10"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
            <button
              type="button"
              aria-label={showNewPassword ? t("actions.hidePassword") : t("actions.showPassword")}
              title={showNewPassword ? t("actions.hidePassword") : t("actions.showPassword")}
              onClick={() => setShowNewPassword((value) => !value)}
              className="absolute inset-y-0 right-0 inline-flex w-10 items-center justify-center"
              style={{ color: "var(--muted)" }}
            >
              {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          {t("fields.confirmPassword")}
          <div className="relative">
            <input
              type={showConfirmPassword ? "text" : "password"}
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              minLength={MIN_PASSWORD_LENGTH}
              title={t("errors.passwordLengthExact")}
              className="h-10 w-full rounded-md border px-3 pr-10"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
            <button
              type="button"
              aria-label={showConfirmPassword ? t("actions.hidePassword") : t("actions.showPassword")}
              title={showConfirmPassword ? t("actions.hidePassword") : t("actions.showPassword")}
              onClick={() => setShowConfirmPassword((value) => !value)}
              className="absolute inset-y-0 right-0 inline-flex w-10 items-center justify-center"
              style={{ color: "var(--muted)" }}
            >
              {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
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
