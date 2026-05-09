import type { BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { resolveGplPriceLevelMeta } from "@/features/backoffice/lib/gpl-field-labels";

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
  return resolveGplPriceLevelMeta(key);
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
