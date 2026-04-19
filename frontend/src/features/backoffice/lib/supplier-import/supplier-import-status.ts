import type { BackofficeSupplierPriceList } from "@/features/backoffice/types/suppliers.types";

export function findLatestPriceListStats(rows: BackofficeSupplierPriceList[]) {
  const latestPriceList = rows[0];
  const latestDownloaded = rows.find((item) => Boolean(item.downloaded_at));
  const latestImported = rows.find((item) => Boolean(item.imported_at));
  const latestErrored = rows.find((item) => Boolean(item.last_error_message));
  const firstDownloadable = rows.find((item) => item.download_available);
  const firstImportable = rows.find((item) => item.import_available);

  return {
    latestPriceList,
    latestDownloaded,
    latestImported,
    latestErrored,
    firstDownloadable,
    firstImportable,
  };
}
