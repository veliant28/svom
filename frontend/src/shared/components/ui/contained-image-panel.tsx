import Image from "next/image";

type ContainedImagePanelProps = {
  imageUrl?: string | null;
  className?: string;
  backgroundColor?: string;
  alt?: string;
};

export function ContainedImagePanel({
  imageUrl,
  className,
  backgroundColor = "var(--surface-2)",
  alt = "",
}: ContainedImagePanelProps) {
  return (
    <div
      className={`relative overflow-hidden flex items-center justify-center ${className ?? ""}`}
      style={{ backgroundColor }}
    >
      {imageUrl ? (
        <>
          <div
            className="pointer-events-none absolute inset-0 scale-110 bg-cover bg-center opacity-35 blur-xl"
            style={{ backgroundImage: `url(${imageUrl})` }}
            aria-hidden="true"
          />
          <Image
            src={imageUrl}
            alt={alt}
            fill
            sizes="(max-width: 768px) 100vw, 33vw"
            className="relative z-10 h-full w-full object-contain object-center"
          />
        </>
      ) : (
        <div className="flex flex-col items-center gap-2 text-[11px] select-none" style={{ color: "var(--muted)" }} aria-hidden="true">
          <div
            className="h-14 w-14 rounded-lg border"
            style={{
              borderColor: "var(--border)",
              background:
                "linear-gradient(160deg, rgba(255,255,255,0.45), rgba(255,255,255,0.1))",
            }}
          />
          <span>NO IMAGE</span>
        </div>
      )}
    </div>
  );
}
