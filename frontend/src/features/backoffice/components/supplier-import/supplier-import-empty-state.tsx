type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SupplierImportFooter({
  t,
  suppliersCount,
}: {
  t: Translator;
  suppliersCount: number;
}) {
  return (
    <p className="text-xs" style={{ color: "var(--muted)" }}>
      {t("footer.availableSuppliers", { count: suppliersCount })}
    </p>
  );
}
