from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers, status
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.services import MatchingReviewService
from apps.catalog.models import Product
from apps.supplier_imports.models import SupplierRawOffer


class ConfirmMatchActionSerializer(serializers.Serializer):
    raw_offer_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    note = serializers.CharField(required=False, allow_blank=True)


class IgnoreOfferActionSerializer(serializers.Serializer):
    raw_offer_id = serializers.UUIDField()
    note = serializers.CharField(required=False, allow_blank=True)


class RetryMatchingActionSerializer(serializers.Serializer):
    raw_offer_id = serializers.UUIDField()
    note = serializers.CharField(required=False, allow_blank=True)


class BulkRawOfferActionSerializer(serializers.Serializer):
    raw_offer_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    note = serializers.CharField(required=False, allow_blank=True)


class ManualMatchItemSerializer(serializers.Serializer):
    raw_offer_id = serializers.UUIDField()
    product_id = serializers.UUIDField()


class ApplyManualMatchesSerializer(serializers.Serializer):
    mappings = ManualMatchItemSerializer(many=True, allow_empty=False)
    note = serializers.CharField(required=False, allow_blank=True)


class ConfirmMatchActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = ConfirmMatchActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_offer_id = str(serializer.validated_data["raw_offer_id"])
        product_id = str(serializer.validated_data["product_id"])

        try:
            raw_offer = SupplierRawOffer.objects.select_related("supplier", "source", "matched_product").get(id=raw_offer_id)
            product = Product.objects.get(id=product_id)
        except ObjectDoesNotExist:
            return Response({"detail": "Raw offer or product not found."}, status=status.HTTP_404_NOT_FOUND)

        result = MatchingReviewService().confirm_match(
            raw_offer=raw_offer,
            product=product,
            actor=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(result, status=status.HTTP_200_OK)


class IgnoreOfferActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = IgnoreOfferActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_offer_id = str(serializer.validated_data["raw_offer_id"])

        try:
            raw_offer = SupplierRawOffer.objects.select_related("supplier", "source", "matched_product").get(id=raw_offer_id)
        except ObjectDoesNotExist:
            return Response({"detail": "Raw offer not found."}, status=status.HTTP_404_NOT_FOUND)

        result = MatchingReviewService().ignore_offer(
            raw_offer=raw_offer,
            actor=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(result, status=status.HTTP_200_OK)


class RetryMatchingActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = RetryMatchingActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_offer_id = str(serializer.validated_data["raw_offer_id"])

        try:
            raw_offer = SupplierRawOffer.objects.select_related("supplier", "source", "matched_product").get(id=raw_offer_id)
        except ObjectDoesNotExist:
            return Response({"detail": "Raw offer not found."}, status=status.HTTP_404_NOT_FOUND)

        result = MatchingReviewService().retry_matching(
            raw_offer=raw_offer,
            actor=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(result, status=status.HTTP_200_OK)


class BulkAutoMatchActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = BulkRawOfferActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_offers = list(
            SupplierRawOffer.objects.select_related("supplier", "source", "matched_product").filter(
                id__in=serializer.validated_data["raw_offer_ids"]
            )
        )

        stats = MatchingReviewService().bulk_auto_match(
            raw_offers=raw_offers,
            actor=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(
            {
                "processed": stats.processed,
                "matched": stats.matched,
                "ignored": stats.ignored,
                "updated": stats.updated,
            },
            status=status.HTTP_200_OK,
        )


class BulkIgnoreActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = BulkRawOfferActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_offers = list(
            SupplierRawOffer.objects.select_related("supplier", "source", "matched_product").filter(
                id__in=serializer.validated_data["raw_offer_ids"]
            )
        )

        stats = MatchingReviewService().bulk_ignore(
            raw_offers=raw_offers,
            actor=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(
            {
                "processed": stats.processed,
                "matched": stats.matched,
                "ignored": stats.ignored,
                "updated": stats.updated,
            },
            status=status.HTTP_200_OK,
        )


class ApplyManualMatchesActionAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = ApplyManualMatchesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mappings = [
            {
                "raw_offer_id": str(item["raw_offer_id"]),
                "product_id": str(item["product_id"]),
            }
            for item in serializer.validated_data["mappings"]
        ]

        stats = MatchingReviewService().apply_manual_matches(
            mappings=mappings,
            actor=request.user,
            note=serializer.validated_data.get("note", ""),
        )

        return Response(
            {
                "processed": stats.processed,
                "matched": stats.matched,
                "ignored": stats.ignored,
                "updated": stats.updated,
            },
            status=status.HTTP_200_OK,
        )
