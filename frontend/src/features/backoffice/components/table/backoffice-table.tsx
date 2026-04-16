import type { ReactNode } from "react";

export type BackofficeColumn<T> = {
  key: string;
  label: ReactNode;
  render: (item: T) => ReactNode;
  className?: string;
};

export function BackofficeTable<T>({
  columns,
  rows,
  emptyLabel,
  noHorizontalScroll = false,
}: {
  columns: Array<BackofficeColumn<T>>;
  rows: T[];
  emptyLabel: string;
  noHorizontalScroll?: boolean;
}) {
  if (!rows.length) {
    return (
      <div className="rounded-xl border p-6 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        {emptyLabel}
      </div>
    );
  }

  return (
    <div
      className={`${noHorizontalScroll ? "overflow-x-hidden" : "overflow-x-auto"} rounded-xl border`}
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <table className={`w-full border-collapse text-sm ${noHorizontalScroll ? "table-fixed" : "min-w-[720px]"}`}>
        <thead>
          <tr style={{ backgroundColor: "var(--surface-2)" }}>
            {columns.map((column) => (
              <th
                key={column.key}
                className={`px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide ${noHorizontalScroll ? "whitespace-normal break-words" : ""} ${column.className ?? ""}`}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t" style={{ borderColor: "var(--border)" }}>
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-3 py-2 align-top ${noHorizontalScroll ? "whitespace-normal break-words" : ""} ${column.className ?? ""}`}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
