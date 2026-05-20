"use client";

type ShortToggleOption<T extends string> = {
  value: T;
  label: string;
  activeColor?: string;
};

export function ShortToggle<T extends string>({
  value,
  options,
  onChange,
  disabled = false,
  ariaLabel,
  className = "",
}: {
  value: T;
  options: ShortToggleOption<T>[];
  onChange: (value: T) => void;
  disabled?: boolean;
  ariaLabel?: string;
  className?: string;
}) {
  if (options.length !== 2) {
    return null;
  }
  const leftOption = options[0];
  const rightOption = options[1];
  const isRightActive = value === rightOption.value;
  const nextValue = isRightActive ? leftOption.value : rightOption.value;

  return (
    <div
      className={`inline-flex items-center gap-2 ${className}`}
      role="group"
      aria-label={ariaLabel}
    >
      <span
        className="text-[11px] font-semibold"
        style={{ color: "var(--text)" }}
      >
        {leftOption.label}
      </span>

      <div
        className="relative inline-flex h-5 w-10 shrink-0 items-center justify-center rounded-full outline-offset-2"
        style={{
          borderWidth: 0,
          borderStyle: "solid",
          borderColor: "rgb(0 0 0)",
        }}
      >
        <span
          className="absolute block h-4 w-9 rounded-full border-0 transition-colors duration-200 ease-in-out"
          style={{
            backgroundColor: isRightActive ? (rightOption.activeColor || "#2563eb") : "oklch(0.928 0.006 264.531)",
            boxShadow: "oklab(0.21 -0.00316127 -0.0338527 / 0.05) 0px 0px 0px 1px inset",
          }}
        />
        <span
          className="absolute left-0 top-0 block h-5 w-5 rounded-full border bg-white transition-transform duration-200 ease-in-out"
          style={{
            borderColor: "oklch(0.872 0.01 258.338)",
            boxShadow: "rgba(0, 0, 0, 0.05) 0px 1px 2px 0px",
            transform: isRightActive ? "translateX(20px)" : "translateX(0px)",
            transitionTimingFunction: "cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
        <input
          type="checkbox"
          name="setting"
          aria-label={ariaLabel}
          checked={isRightActive}
          disabled={disabled}
          className="absolute right-0 top-0 h-5 w-10 cursor-pointer rounded-full opacity-0 disabled:cursor-not-allowed"
          onChange={() => {
            onChange(nextValue);
          }}
        />
      </div>

      <span
        className="text-[11px] font-semibold"
        style={{ color: "var(--text)" }}
      >
        {rightOption.label}
      </span>
    </div>
  );
}
