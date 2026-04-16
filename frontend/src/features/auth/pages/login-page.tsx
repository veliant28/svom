import { useTranslations } from "next-intl";

import { LoginForm } from "@/features/auth/components/login-form";

export function LoginPage() {
  const t = useTranslations("auth");

  return (
    <section className="mx-auto grid max-w-6xl gap-4 px-4 py-8 lg:grid-cols-[420px_1fr]">
      <div className="rounded-xl border p-5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          {t("subtitle")}
        </p>

        <div className="mt-4">
          <LoginForm />
        </div>
      </div>

      <div className="rounded-xl border p-5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <h2 className="text-lg font-semibold">{t("demo.title")}</h2>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          {t("demo.description")}
        </p>
        <p className="mt-3 text-xs" style={{ color: "var(--muted)" }}>
          {t("demo.credentials")}
        </p>
      </div>
    </section>
  );
}
