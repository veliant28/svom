export function StatCard({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
}) {
  return (
    <article
      className="rounded-2xl border p-4"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "var(--surface)",
      }}
    >
      <p className="text-xs uppercase tracking-[0.14em]" style={{ color: "var(--muted)" }}>
        {title}
      </p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      {subtitle ? (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
          {subtitle}
        </p>
      ) : null}
    </article>
  );
}
