"use client";

export type SeoWorkspace = "seo" | "google";

export function SeoWorkspaceSwitcher({
  active,
  onChange,
  labels,
  ariaLabel,
}: {
  active: SeoWorkspace;
  onChange: (next: SeoWorkspace) => void;
  labels: Record<SeoWorkspace, string>;
  ariaLabel: string;
}) {
  return (
    <div
      className="inline-flex items-center gap-2 rounded-xl border p-1"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      role="tablist"
      aria-label={ariaLabel}
    >
      {(Object.keys(labels) as SeoWorkspace[]).map((workspace) => (
        <button
          key={workspace}
          type="button"
          role="tab"
          aria-selected={workspace === active}
          className="h-10 rounded-lg border px-4 text-sm transition-colors"
          style={{
            borderColor: workspace === active ? "var(--text)" : "var(--border)",
            backgroundColor: workspace === active ? "var(--surface)" : "var(--surface-2)",
            fontWeight: workspace === active ? 700 : 500,
          }}
          onClick={() => onChange(workspace)}
        >
          {labels[workspace]}
        </button>
      ))}
    </div>
  );
}
