export type WarehouseSegment = {
  key: string;
  value: string;
  qty: number | null;
};

function parseWarehouseQty(value: string): number | null {
  const normalized = value
    .replace(",", ".")
    .replace(/[^\d.-]/g, "")
    .trim();
  if (!normalized) {
    return null;
  }
  const qty = Number(normalized);
  if (!Number.isFinite(qty)) {
    return null;
  }
  return qty;
}

function warehouseVisualRank(qty: number | null): number {
  if (qty === null || !Number.isFinite(qty)) {
    return Number.MAX_SAFE_INTEGER;
  }
  if (qty >= 7) {
    return 1;
  }
  if (qty >= 4) {
    return 2;
  }
  if (qty >= 1) {
    return 3;
  }
  if (qty === 0) {
    return 4;
  }
  return Number.MAX_SAFE_INTEGER;
}

export function extractWarehouses(payload: Record<string, unknown>): WarehouseSegment[] {
  const entries = Object.entries(payload);
  const result: Array<WarehouseSegment & { index: number }> = [];

  for (const [key, value] of entries) {
    const label = key.toLowerCase();
    const isWarehouse =
      label.includes("склад")
      || label.includes("warehouse")
      || label.includes("обл")
      || label.startsWith("count_warehouse_");
    if (!isWarehouse) {
      continue;
    }

    const normalized = String(value ?? "").trim();
    if (!normalized) {
      continue;
    }

    result.push({
      key,
      value: normalized,
      qty: parseWarehouseQty(normalized),
      index: result.length,
    });
  }

  return result
    .sort((left, right) => {
      const rankCompare = warehouseVisualRank(left.qty) - warehouseVisualRank(right.qty);
      if (rankCompare !== 0) {
        return rankCompare;
      }
      if (left.qty !== null && right.qty !== null) {
        const qtyCompare = right.qty - left.qty;
        if (qtyCompare !== 0) {
          return qtyCompare;
        }
      } else if (left.qty === null && right.qty !== null) {
        return 1;
      } else if (left.qty !== null && right.qty === null) {
        return -1;
      }
      return left.index - right.index;
    })
    .map(({ key, value, qty }) => ({ key, value, qty }));
}

export function compactWarehouseName(key: string): string {
  const normalized = key
    .replace(/^count_warehouse_/i, "")
    .replace(/^warehouse[_\s-]*/i, "")
    .replace(/_/g, " ")
    .trim();

  if (!normalized) {
    return "Склад";
  }
  return normalized;
}

export function resolveWarehouseTone(qty: number | null): { border: string; background: string; text: string } {
  if (qty === 0) {
    return {
      border: "#94a3b8",
      background: "#94a3b8",
      text: "#ffffff",
    };
  }
  if (qty !== null && qty > 0 && qty <= 3) {
    return {
      border: "#e11d48",
      background: "#e11d48",
      text: "#ffffff",
    };
  }
  if (qty !== null && qty >= 4 && qty <= 6) {
    return {
      border: "#f59e0b",
      background: "#f59e0b",
      text: "#111827",
    };
  }
  if (qty !== null && qty >= 7) {
    return {
      border: "#16a34a",
      background: "#16a34a",
      text: "#ffffff",
    };
  }
  return {
    border: "var(--border)",
    background: "var(--surface-2)",
    text: "var(--text)",
  };
}

export function formatWarehouseQty(qty: number | null): string {
  if (qty === null) {
    return "?";
  }
  const normalized = Math.max(0, Math.trunc(qty));
  if (normalized > 99) {
    return "99+";
  }
  return String(normalized);
}
