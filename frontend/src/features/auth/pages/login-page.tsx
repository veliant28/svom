import { useTranslations } from "next-intl";

import { LoginForm } from "@/features/auth/components/login-form";
import { Link } from "@/i18n/navigation";

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
        <h2 className="text-lg font-semibold">{t("accountAccess.title")}</h2>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          {t("accountAccess.description")}
        </p>

        <div className="mt-4 grid gap-3">
          <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="text-sm font-semibold">{t("accountAccess.forgot.title")}</p>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
              {t("accountAccess.forgot.description")}
            </p>
            <Link
              href="/forgot-password"
              className="mt-3 inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              {t("accountAccess.forgot.action")}
            </Link>
          </div>

          <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="text-sm font-semibold">{t("accountAccess.register.title")}</p>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
              {t("accountAccess.register.description")}
            </p>
            <Link
              href="/register"
              className="mt-3 inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
            >
              {t("accountAccess.register.action")}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
