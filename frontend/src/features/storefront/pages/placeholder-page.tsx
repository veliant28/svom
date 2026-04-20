export function PlaceholderPage({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-3xl font-bold">{title}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {subtitle}
      </p>
    </section>
  );
}
