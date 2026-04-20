import { useTheme } from "@/shared/components/theme/theme-provider";

export function PaymentProviderSwitcher({
  active,
  onChange,
  labels,
}: {
  active: "mono" | "nova";
  onChange: (provider: "mono" | "nova") => void;
  labels: {
    mono: string;
    nova: string;
  };
}) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const monoActiveBackground = isDark ? "#ffffff" : "#000000";
  const monoActiveText = isDark ? "#111111" : "#ffffff";
  const novaActiveBackground = "#690DD3";

  return (
    <div
      className="inline-flex items-center gap-2 rounded-xl border p-1"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      role="tablist"
    >
      <button
        type="button"
        role="tab"
        aria-selected={active === "mono"}
        className="h-10 rounded-lg border px-4 text-sm transition-colors"
        style={{
          borderColor: active === "mono" ? monoActiveBackground : "var(--border)",
          backgroundColor: active === "mono" ? monoActiveBackground : "var(--surface-2)",
          color: active === "mono" ? monoActiveText : "var(--text)",
          fontWeight: active === "mono" ? 700 : 500,
        }}
        onClick={() => onChange("mono")}
      >
        {labels.mono}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={active === "nova"}
        className="h-10 rounded-lg border px-4 text-sm transition-colors"
        style={{
          borderColor: active === "nova" ? novaActiveBackground : "var(--border)",
          backgroundColor: active === "nova" ? novaActiveBackground : "var(--surface-2)",
          color: active === "nova" ? "#ffffff" : "var(--text)",
          fontWeight: active === "nova" ? 700 : 500,
        }}
        onClick={() => onChange("nova")}
      >
        {labels.nova}
      </button>
    </div>
  );
}
