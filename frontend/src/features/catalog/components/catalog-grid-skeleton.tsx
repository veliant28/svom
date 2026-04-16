export function CatalogGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, index) => (
        <article
          key={index}
          className="animate-pulse rounded-xl border p-4"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        >
          <div className="h-28 rounded-md" style={{ backgroundColor: "var(--surface-2)" }} />
          <div className="mt-3 h-4 w-3/4 rounded" style={{ backgroundColor: "var(--surface-2)" }} />
          <div className="mt-2 h-3 w-1/2 rounded" style={{ backgroundColor: "var(--surface-2)" }} />
          <div className="mt-4 h-6 w-24 rounded" style={{ backgroundColor: "var(--surface-2)" }} />
        </article>
      ))}
    </div>
  );
}
