"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  confirmBackofficeMatch,
  getBackofficeMatchingCandidates,
  getBackofficeMatchingReview,
  ignoreBackofficeOffer,
  retryBackofficeMatching,
} from "@/features/backoffice/api/backoffice-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";

export function MatchingReviewPage({ reviewId }: { reviewId: string }) {
  const t = useTranslations("backoffice.matching.review");
  const [selectedProductId, setSelectedProductId] = useState<string>("");
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const reviewQueryFn = useCallback((token: string) => getBackofficeMatchingReview(token, reviewId), [reviewId]);
  const candidatesQueryFn = useCallback((token: string) => getBackofficeMatchingCandidates(token, reviewId), [reviewId]);

  const review = useBackofficeQuery(reviewQueryFn, [reviewId]);
  const candidates = useBackofficeQuery(candidatesQueryFn, [reviewId]);

  const candidateRows = candidates.data?.results ?? [];

  const preselectedProduct = useMemo(() => {
    if (selectedProductId) {
      return selectedProductId;
    }
    if (review.data?.matched_product) {
      return review.data.matched_product;
    }
    if (candidateRows.length === 1) {
      return candidateRows[0].id;
    }
    return "";
  }, [selectedProductId, review.data?.matched_product, candidateRows]);

  async function confirm() {
    if (!review.token || !preselectedProduct) return;
    try {
      await confirmBackofficeMatch(review.token, {
        raw_offer_id: reviewId,
        product_id: preselectedProduct,
      });
      showSuccess(t("messages.confirmed"));
      await review.refetch();
      await candidates.refetch();
    } catch (error: unknown) {
      showApiError(error, t("messages.actionFailed"));
    }
  }

  async function ignore() {
    if (!review.token) return;
    try {
      await ignoreBackofficeOffer(review.token, { raw_offer_id: reviewId });
      showSuccess(t("messages.ignored"));
      await review.refetch();
      await candidates.refetch();
    } catch (error: unknown) {
      showApiError(error, t("messages.actionFailed"));
    }
  }

  async function retry() {
    if (!review.token) return;
    try {
      await retryBackofficeMatching(review.token, { raw_offer_id: reviewId });
      showSuccess(t("messages.retried"));
      await review.refetch();
      await candidates.refetch();
    } catch (error: unknown) {
      showApiError(error, t("messages.actionFailed"));
    }
  }

  return (
    <section>
      <PageHeader
        title={t("title")}
        description={t("subtitle")}
        actions={
          <>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void retry();
              }}
            >
              {t("actions.retry")}
            </button>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void ignore();
              }}
            >
              {t("actions.ignore")}
            </button>
            <button
              type="button"
              className="h-9 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void confirm();
              }}
              disabled={!preselectedProduct}
            >
              {t("actions.confirm")}
            </button>
          </>
        }
      />

      <AsyncState isLoading={review.isLoading} error={review.error} empty={!review.data} emptyLabel={t("states.empty")}> 
        {review.data ? (
          <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
            <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <h2 className="text-sm font-semibold">{t("offer.title")}</h2>
              <div className="mt-3 grid gap-2 text-sm">
                <p><strong>{t("offer.supplier")}: </strong>{review.data.supplier_code}</p>
                <p><strong>{t("offer.externalSku")}: </strong>{review.data.external_sku}</p>
                <p><strong>{t("offer.article")}: </strong>{review.data.article}</p>
                <p><strong>{t("offer.brand")}: </strong>{review.data.brand_name}</p>
                <p><strong>{t("offer.productName")}: </strong>{review.data.product_name}</p>
                <p><strong>{t("offer.price")}: </strong>{review.data.price ?? "-"} {review.data.currency}</p>
                <p><strong>{t("offer.status")}: </strong><StatusChip status={review.data.match_status} /></p>
                {review.data.match_reason ? <p><strong>{t("offer.reason")}: </strong>{review.data.match_reason}</p> : null}
              </div>
            </section>

            <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              <h2 className="text-sm font-semibold">{t("candidates.title")}</h2>
              <AsyncState
                isLoading={candidates.isLoading}
                error={candidates.error}
                empty={candidateRows.length === 0}
                emptyLabel={t("states.noCandidates")}
              >
                <div className="mt-3 grid gap-2">
                  {candidateRows.map((candidate) => (
                    <label
                      key={candidate.id}
                      className="flex cursor-pointer items-start gap-3 rounded-lg border p-3"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    >
                      <input
                        type="radio"
                        checked={preselectedProduct === candidate.id}
                        onChange={() => setSelectedProductId(candidate.id)}
                      />
                      <div>
                        <p className="font-semibold">{candidate.name}</p>
                        <p className="text-xs" style={{ color: "var(--muted)" }}>
                          {candidate.sku} / {candidate.article}
                        </p>
                        <p className="text-xs" style={{ color: "var(--muted)" }}>
                          {candidate.brand_name} / {candidate.category_name}
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
              </AsyncState>
            </section>
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
