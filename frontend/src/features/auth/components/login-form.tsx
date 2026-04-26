"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { resolveLoginError } from "@/features/auth/lib/login-error";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function LoginForm() {
  const t = useTranslations("auth");
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, isAuthenticated } = useAuth();
  const { showError } = useStorefrontFeedback();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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
        setIsSubmitting(true);

        try {
          await login({ email, password });
          const nextPath = searchParams.get("next");
          if (nextPath && nextPath.startsWith("/")) {
            router.push(nextPath);
          } else {
            router.push("/");
          }
        } catch (error: unknown) {
          const resolved = resolveLoginError(error);
          showError(t(resolved.translationKey, resolved.values));
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

      <label className="flex flex-col gap-1 text-xs">
        {t("fields.password")}
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          className="h-10 rounded-md border px-3"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        />
      </label>

      <button
        type="submit"
        disabled={isSubmitting}
        className="h-10 rounded-md border px-3 text-sm disabled:opacity-60"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        {isSubmitting ? t("actions.loggingIn") : t("actions.login")}
      </button>

    </form>
  );
}
