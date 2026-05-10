import type { BackofficeStatusChipTone } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import type { BackofficeCatalogProduct } from "@/features/backoffice/types/catalog.types";

type ProductPriceStatus = BackofficeCatalogProduct["productprice_status"];

export function resolveProductPriceStatusTone(status: ProductPriceStatus): BackofficeStatusChipTone {
  if (status === "has_price") {
    return "success";
  }
  if (status === "no_product_price") {
    return "warning";
  }
  if (status === "invalid_offer") {
    return "error";
  }
  return "gray";
}

export function resolveProductPriceStatusLabel(status: ProductPriceStatus): string {
  if (status === "has_price") {
    return "has_price";
  }
  if (status === "no_product_price") {
    return "no_product_price";
  }
  if (status === "invalid_offer") {
    return "invalid_offer";
  }
  return "no_available_offer";
}

export function formatWarehouseSummaryLabel(summary: BackofficeCatalogProduct["warehouse_summary"]): string {
  if (!summary || summary.warehouse_total_count <= 0) {
    return "-";
  }
  return `${summary.warehouse_nonzero_count}/${summary.warehouse_total_count} складів`;
}
