export type BackofficeMatchingSummary = {
  unmatched: number;
  conflicts: number;
  auto_matched: number;
  manually_matched: number;
  ignored: number;
};

export type BackofficeMatchingCandidateProduct = {
  id: string;
  name: string;
  sku: string;
  article: string;
  brand_name: string;
  category_name: string;
};
