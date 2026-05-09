import type { BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";

export type GplPriceLevelMeta = {
  badgeLabel: string;
  tone: BackofficeStatusChipTone;
  order: number;
};

const GPL_PRICE_LEVEL_META_BY_NORMALIZED_KEY: Record<string, GplPriceLevelMeta> = {
  pricetype1: { badgeLabel: "ОПТ2", tone: "success", order: 2 },
  pricetype2: { badgeLabel: "ОПТ4", tone: "orange", order: 4 },
  pricetype9: { badgeLabel: "ОПТ10", tone: "red", order: 10 },
  pricetype10: { badgeLabel: "РРЦ", tone: "blue", order: 100 },
};

const GPL_WAREHOUSE_LABEL_BY_KEY: Record<string, string> = {
  count_warehouse_1: "Склад ПЛТВ",
  count_warehouse_2: "Склад ТРНП",
  count_warehouse_4: "Склад БРСП",
};

export function resolveGplPriceLevelMeta(key: string): GplPriceLevelMeta | null {
  const normalized = key.toLowerCase().replace(/[\s_-]/g, "");
  if (GPL_PRICE_LEVEL_META_BY_NORMALIZED_KEY[normalized]) {
    return GPL_PRICE_LEVEL_META_BY_NORMALIZED_KEY[normalized];
  }
  if (normalized.startsWith("pricetype1currency")) {
    return GPL_PRICE_LEVEL_META_BY_NORMALIZED_KEY.pricetype1;
  }
  if (normalized.startsWith("pricetype2currency")) {
    return GPL_PRICE_LEVEL_META_BY_NORMALIZED_KEY.pricetype2;
  }
  if (normalized.startsWith("pricetype9currency")) {
    return GPL_PRICE_LEVEL_META_BY_NORMALIZED_KEY.pricetype9;
  }
  if (normalized.startsWith("pricetype10currency")) {
    return GPL_PRICE_LEVEL_META_BY_NORMALIZED_KEY.pricetype10;
  }

  if (normalized.includes("ррц") || normalized.includes("rrc")) {
    return { badgeLabel: "РРЦ", tone: "blue", order: 100 };
  }
  if (normalized.includes("опт2") || normalized.includes("opt2")) {
    return { badgeLabel: "ОПТ2", tone: "success", order: 2 };
  }
  if (normalized.includes("опт4") || normalized.includes("opt4")) {
    return { badgeLabel: "ОПТ4", tone: "orange", order: 4 };
  }
  if (normalized.includes("опт10") || normalized.includes("opt10")) {
    return { badgeLabel: "ОПТ10", tone: "red", order: 10 };
  }
  return null;
}

export function resolveGplWarehouseLabel(key: string): string | null {
  const normalizedKey = key.toLowerCase();
  return GPL_WAREHOUSE_LABEL_BY_KEY[normalizedKey] || null;
}
