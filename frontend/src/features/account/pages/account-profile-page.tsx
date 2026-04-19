"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { AccountAuthRequired } from "@/features/account/components/account-auth-required";
import { AccountPasswordForm } from "@/features/account/components/profile/account-password-form";
import { AccountProfileForm, type AccountProfileFormValues } from "@/features/account/components/profile/account-profile-form";
import { changePassword } from "@/features/auth/api/change-password";
import { updateProfile } from "@/features/auth/api/update-profile";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function AccountProfilePage() {
  const t = useTranslations("auth.profile");
  const { token, user, isAuthenticated, refreshUser } = useAuth();
  const { showApiError, showSuccess } = useStorefrontFeedback();
  const [isProfileSubmitting, setIsProfileSubmitting] = useState(false);
  const [isPasswordSubmitting, setIsPasswordSubmitting] = useState(false);

  if (!isAuthenticated || !user) {
    return <AccountAuthRequired title={t("title")} message={t("authRequired")} loginLabel={t("goToLogin")} />;
  }

  async function handleProfileSubmit(values: AccountProfileFormValues) {
    if (!token) {
      return;
    }

    setIsProfileSubmitting(true);
    try {
      await updateProfile(token, values);
      await refreshUser();
      showSuccess(t("messages.profileUpdated"));
    } catch (error) {
      showApiError(error, t("errors.profileUpdateFailed"));
    } finally {
      setIsProfileSubmitting(false);
    }
  }

  async function handlePasswordSubmit(payload: { current_password: string; new_password: string }) {
    if (!token) {
      return;
    }

    setIsPasswordSubmitting(true);
    try {
      await changePassword(token, payload);
      showSuccess(t("messages.passwordUpdated"));
    } catch (error) {
      showApiError(error, t("errors.passwordUpdateFailed"));
    } finally {
      setIsPasswordSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {t("subtitle")}
      </p>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <AccountProfileForm
          user={user}
          isSubmitting={isProfileSubmitting}
          onSubmit={handleProfileSubmit}
        />

        <AccountPasswordForm
          isSubmitting={isPasswordSubmitting}
          onSubmit={handlePasswordSubmit}
        />
      </div>
    </section>
  );
}
