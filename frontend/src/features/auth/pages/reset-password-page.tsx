import { useTranslations } from "next-intl";

import { ResetPasswordForm } from "@/features/auth/components/reset-password-form";

export function ResetPasswordPage({
  uid,
  token,
}: {
  uid: string;
  token: string;
}) {
  const t = useTranslations("auth.resetPassword");

  return (
    <section className="mx-auto max-w-xl px-4 py-8">
      <div className="rounded-xl border p-5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          {t("subtitle")}
        </p>

        <div className="mt-4">
          <ResetPasswordForm uid={uid} token={token} />
        </div>
      </div>
    </section>
  );
}
