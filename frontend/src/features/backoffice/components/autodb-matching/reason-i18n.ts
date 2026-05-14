type Translator = (key: string, values?: Record<string, string | number>) => string;

function safeTranslate(t: Translator, key: string, fallback: string): string {
  try {
    return t(key as never);
  } catch {
    return fallback;
  }
}

function humanize(value: string): string {
  const raw = String(value || "").trim();
  if (!raw) return "-";
  return raw.replaceAll("_", " ");
}

const EXACT_REASON_KEY: Record<string, string> = {
  "missing auto_db supplier_id": "missingSupplierId",
  "missing supplier_id or canonical_article": "missingSupplierOrArticle",
  "local deterministic article not found": "localNotFound",
  "local article found but article_prd/prd linkage missing": "localMissingLinkage",
  "local deterministic lookup found linked article": "localFoundLinked",
  "remote deterministic lookup found article": "remoteFound",
  "remote deterministic lookup missed": "remoteMissed",
  "remote quota cooldown active": "remoteQuotaCooldown",
  "missing_supplier_id": "missingSupplierId",
  "missing_article": "missingArticle",
  "missing_brand": "missingBrand",
  "no_allowed_source_type": "noAllowedSourceType",
  "blocked_raw_offer_article": "blockedRawOfferArticle",
  "filtered_by_existing_rule": "filteredByRule",
  "cannot use product article fallback": "cannotUseProductArticleFallback",
  "cannot_use_product_article_fallback": "cannotUseProductArticleFallback",
  "trusted auto_db link already exists": "trustedLinkExists",
  needs_review: "needsReview",
  needs_review_trusted_conflict: "needsReviewConflict",
  skipped_multi_offer_conflict: "skippedConflict",
  skipped_split_product_candidate: "splitCandidate",
  product_quality_quarantine: "qualityQuarantine",
  quarantine_released_by_split_v2: "quarantineReleased",
  split_artifact_cleanup_ignored: "splitCleanupIgnored",
  manual_bind_from_backoffice: "manualBindFromBackoffice",
  "safe_link_candidate can be applied by a later guarded linker": "safeLinkCandidateLater",
  "source-aware deterministic article candidate": "sourceAwareArticleCandidate",
  "clone sync plan ready; article_images excluded": "cloneSyncPlanReady",
  "attributes/fitments only; images disabled": "attributesFitmentsOnly",
  "no deterministic supplier candidate in auto_db_pro.suppliers": "noDeterministicSupplierCandidate",
  "no deterministic candidate in auto_db_pro.suppliers": "noDeterministicSupplierCandidate",
  "raw brand normalizes to empty value; resolver falls into needs_alias": "rawBrandNormalizedEmpty",
  "brand requires explicit human-approved mapping": "brandRequiresMapping",
  "multiple local auto_db suppliers match normalized brand": "multipleLocalSuppliersMatchBrand",
  candidates_zero: "candidatesZero",
  ok: "ok",
  insufficient_probe_n: "insufficientProbeN",
  hit_rate_too_low: "hitRateTooLow",
  "no deterministic candidate": "noDeterministicCandidate",
  "single deterministic supplier candidate": "singleDeterministicSupplierCandidate",
  "multiple deterministic supplier candidates": "multipleDeterministicSupplierCandidates",
  "single deterministic candidate": "singleDeterministicCandidate",
  "single deterministic candidate exists but unresolved by coverage policy": "singleCandidateCoverageUnresolved",
  "multiple deterministic candidates": "multipleDeterministicCandidates",
  "no deterministic local supplier candidate": "noDeterministicLocalSupplierCandidate",
  "invalid brand value": "invalidBrandValue",
  "too short normalized brand": "tooShortNormalizedBrand",
  "single deterministic local candidate": "singleDeterministicLocalCandidate",
  "multiple deterministic local candidates": "multipleDeterministicLocalCandidates",
  "brand token looks non-standard": "brandTokenNonStandard",
  "no remote supplier candidate": "noRemoteSupplierCandidate",
  "single deterministic remote supplier candidate": "singleDeterministicRemoteSupplierCandidate",
  "multiple deterministic remote suppliers": "multipleDeterministicRemoteSuppliers",
  "existing products already bound to different supplier": "existingProductsBoundDifferentSupplier",
  "all products manually locked": "allProductsManuallyLocked",
  split_product_deactivated: "splitProductDeactivated",
  orphan_inactive_split_product: "orphanInactiveSplitProduct",
  "deterministic v3 canonical article has article_prd/prd linkage": "deterministicV3HasLinkage",
  "deterministic v3 evidence is missing required linkage": "deterministicV3MissingLinkage",
  "conflicting product.autodb_supplier_id values in brand group": "conflictingProductSupplierIdsInBrand",
  multi_offer_guard: "multiOfferGuard",
  no_trusted_article: "noTrustedArticle",
  missing_product_article: "missingProductArticle",
  "brand in non-tecdoc blocked list": "brandNonTecdocBlocked",
  "brand in unsafe/split blocked list": "brandUnsafeSplitBlocked",
  "resolved via existing approved auto_db alias": "resolvedViaApprovedAlias",
  "alias supplier missing in auto_db_pro.suppliers": "aliasSupplierMissing",
  "deterministic diacritics/trademark variant match": "deterministicVariantMatch",
  "multiple supplier candidates after deterministic variant matching": "multipleCandidatesAfterVariantMatching",
  "existing product.autodb_supplier_id points to different supplier": "existingProductSupplierDiffers",
  "all products for brand are manually locked": "allProductsForBrandLocked",
  "all products already bound to same supplier": "allProductsAlreadyBoundSameSupplier",
  "create deterministic alias": "createDeterministicAlias",
  "alias already exists with same supplier": "aliasAlreadyExistsSameSupplier",
  "existing alias points to different supplier": "existingAliasDifferentSupplier",
  trusted_link: "trustedLink",
  "no deterministic supplier variant match in auto_db_pro.suppliers": "noDeterministicSupplierVariantMatch",
};

function reasonTranslationKey(reason: string): string | null {
  const normalized = String(reason || "").trim().toLowerCase();
  if (!normalized) return null;
  const exact = EXACT_REASON_KEY[normalized];
  if (exact) return exact;

  if (normalized.startsWith("remote precheck failed:")) return "remotePrecheckFailed";
  if (normalized.startsWith("status ") && normalized.endsWith(" is not clone-sync ready")) return "cloneSyncNotReady";
  if (normalized.startsWith("split_v2_applied_source:")) return "splitAppliedSource";
  if (normalized.startsWith("split_v2_applied_new:")) return "splitAppliedNew";
  if (normalized.startsWith("split_rollback_applied:")) return "splitRollbackApplied";
  if (normalized.startsWith("keep_group=")) return "splitKeepGroup";
  if (normalized.startsWith("move_group=")) return "splitMoveGroup";
  if (normalized.startsWith("restored_offer_ids=")) return "splitRollbackRestored";
  if (normalized.startsWith("status ") && normalized.endsWith(" is not apply-safe")) return "notApplySafeStatus";

  return null;
}

export function translateAutoDbReason(t: Translator, reason: string): string {
  const normalized = String(reason || "").trim();
  if (!normalized) return "-";
  const key = reasonTranslationKey(normalized);
  if (!key) return humanize(normalized);
  return safeTranslate(t, `products.reasonShort.${key}`, humanize(normalized));
}

