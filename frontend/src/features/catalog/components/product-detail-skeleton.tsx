export function ProductDetailSkeleton() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <div className="animate-pulse rounded-xl border p-6" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div className="h-7 w-2/3 rounded" style={{ backgroundColor: "var(--surface-2)" }} />
        <div className="mt-4 h-56 rounded" style={{ backgroundColor: "var(--surface-2)" }} />
        <div className="mt-4 h-4 w-1/2 rounded" style={{ backgroundColor: "var(--surface-2)" }} />
        <div className="mt-2 h-4 w-1/3 rounded" style={{ backgroundColor: "var(--surface-2)" }} />
      </div>
    </section>
  );
}
