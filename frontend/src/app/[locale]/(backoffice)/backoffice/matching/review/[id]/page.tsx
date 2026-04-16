import { MatchingReviewPage } from "@/features/backoffice/pages/matching-review-page";

export default async function MatchingReviewRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MatchingReviewPage reviewId={id} />;
}
