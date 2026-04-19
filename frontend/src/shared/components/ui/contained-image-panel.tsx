type ContainedImagePanelProps = {
  imageUrl?: string | null;
  className?: string;
  backgroundColor?: string;
};

export function ContainedImagePanel({
  imageUrl,
  className,
  backgroundColor = "var(--surface-2)",
}: ContainedImagePanelProps) {
  return (
    <div className={`relative overflow-hidden ${className ?? ""}`} style={{ backgroundColor }}>
      {imageUrl ? (
        <>
          <div
            className="pointer-events-none absolute inset-0 scale-110 bg-cover bg-center opacity-35 blur-xl"
            style={{ backgroundImage: `url(${imageUrl})` }}
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute inset-0 bg-contain bg-center bg-no-repeat"
            style={{ backgroundImage: `url(${imageUrl})` }}
            aria-hidden="true"
          />
        </>
      ) : null}
    </div>
  );
}
