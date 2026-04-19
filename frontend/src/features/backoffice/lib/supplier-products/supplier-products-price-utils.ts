import type { BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";

const PRICE_CHIP_TONES: BackofficeStatusChipTone[] = ["blue", "success", "orange", "red", "info"];

export type PriceLevel = {
  key: string;
  value: string;
  badgeLabel: string;
  tone: BackofficeStatusChipTone;
  order: number;
  index: number;
};

function resolveGplPriceMeta(key: string): { badgeLabel: string; tone: BackofficeStatusChipTone; order: number } | null {
  const normalized = key.toLowerCase().replace(/[\s_-]/g, "");
  if (normalized.includes("ррц") || normalized.includes("rrc")) {
    return { badgeLabel: "РРЦ", tone: "blue", order: 1 };
  }
  if (normalized.includes("опт2") || normalized.includes("opt2")) {
    return { badgeLabel: "ОПТ2", tone: "success", order: 2 };
  }
  if (normalized.includes("опт4") || normalized.includes("opt4")) {
    return { badgeLabel: "ОПТ4", tone: "orange", order: 3 };
  }
  if (normalized.includes("опт10") || normalized.includes("opt10")) {
    return { badgeLabel: "ОПТ10", tone: "red", order: 4 };
  }
  return null;
}

export function extractPriceLevels(payload: Record<string, unknown>, supplierCode: string): PriceLevel[] {
  const entries = Object.entries(payload);
  const result: PriceLevel[] = [];

  for (const [key, value] of entries) {
    const label = key.toLowerCase();
    const gplMeta = supplierCode === "gpl" ? resolveGplPriceMeta(key) : null;
    const isPriceLike = gplMeta !== null || label.includes("ціна") || label.includes("price") || label.includes("ррц") || label.includes("опт") || label.includes("opt");
    if (!isPriceLike) {
      continue;
    }

    const normalized = String(value ?? "").trim();
    if (!normalized) {
      continue;
    }

    if (supplierCode === "gpl") {
      result.push({
        key,
        value: normalized,
        badgeLabel: gplMeta?.badgeLabel ?? key,
        tone: gplMeta?.tone ?? "info",
        order: gplMeta?.order ?? 100 + result.length,
        index: result.length,
      });
      continue;
    }

    result.push({
      key,
      value: normalized,
      badgeLabel: key,
      tone: PRICE_CHIP_TONES[result.length % PRICE_CHIP_TONES.length],
      order: result.length,
      index: result.length,
    });
  }

  return result.sort((left, right) => {
    const orderCompare = left.order - right.order;
    if (orderCompare !== 0) {
      return orderCompare;
    }
    return left.index - right.index;
  });
}
