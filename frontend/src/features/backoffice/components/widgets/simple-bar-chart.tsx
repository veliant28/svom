export function SimpleBarChart({
  title,
  items,
}: {
  title: string;
  items: Array<{ label: string; value: number }>;
}) {
  const max = Math.max(...items.map((item) => item.value), 1);

  return (
    <section
      className="rounded-2xl border p-4"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "var(--surface)",
      }}
    >
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-4 grid gap-3">
        {items.map((item) => {
          const width = Math.max(6, Math.round((item.value / max) * 100));
          return (
            <div key={item.label}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span style={{ color: "var(--muted)" }}>{item.label}</span>
                <span>{item.value}</span>
              </div>
              <div className="h-2 rounded-full" style={{ backgroundColor: "var(--surface-2)" }}>
                <div
                  className="h-2 rounded-full"
                  style={{
                    width: `${width}%`,
                    background: "linear-gradient(90deg, #ff7a18 0%, #ef4444 100%)",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
