"use client";

export function NovapayPaymentCard({
  title,
  selected,
  onSelect,
}: {
  title: string;
  hint: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <div>
      <button
        type="button"
        className="relative inline-flex h-11 w-full items-center justify-center overflow-hidden rounded-md border transition"
        style={{
          borderColor: selected ? "var(--accent)" : "var(--border)",
          backgroundColor: "#690DD3",
          boxShadow: selected ? "0 0 0 2px var(--accent)" : "none",
        }}
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={title}
      >
        <span
          aria-hidden
          className="absolute inset-0 flex items-center justify-center px-[10px] py-[6px]"
        >
          <span
            className="block h-full w-full"
            style={{
              backgroundImage: "url('/icons/novapay.svg')",
              backgroundRepeat: "no-repeat",
              backgroundPosition: "center",
              backgroundSize: "contain",
            }}
          />
        </span>
      </button>
    </div>
  );
}
