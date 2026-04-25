import { Link } from "@/i18n/navigation";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function CheckoutStateMessage({
  t,
  messageKey,
  actionHref,
  actionKey,
}: {
  t: Translator;
  messageKey: string;
  actionHref: "/login" | "/catalog";
  actionKey: string;
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {t(messageKey)}
      </p>
      <Link href={actionHref} className="mt-4 inline-flex rounded-md border px-3 py-2 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        {t(actionKey)}
      </Link>
    </section>
  );
}
