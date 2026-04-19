from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.encoding import smart_str
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.backoffice.api.serializers.nova_poshta_serializer import (
    NovaPoshtaCounterpartyDetailsQuerySerializer,
    NovaPoshtaCounterpartyLookupQuerySerializer,
    NovaPoshtaDeliveryDateLookupQuerySerializer,
    NovaPoshtaLookupQuerySerializer,
    NovaPoshtaPackListLookupQuerySerializer,
    NovaPoshtaSenderProfileSerializer,
    NovaPoshtaStreetLookupQuerySerializer,
    NovaPoshtaTimeIntervalsLookupQuerySerializer,
    NovaPoshtaWarehouseLookupQuerySerializer,
    NovaPoshtaWaybillSummarySerializer,
    OrderNovaPoshtaWaybillSerializer,
    OrderNovaPoshtaWaybillUpsertSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.commerce.models import NovaPoshtaSenderProfile, Order, OrderNovaPoshtaWaybillEvent
from apps.commerce.services.nova_poshta import NovaPoshtaLookupService, NovaPoshtaSenderProfileService, NovaPoshtaWaybillService
from apps.commerce.services.nova_poshta.client import NovaPoshtaApiClient
from apps.commerce.services.nova_poshta.errors import NovaPoshtaIntegrationError
from apps.commerce.services.nova_poshta.tracking_status_catalog import resolve_tracking_status_text


class NovaPoshtaSenderProfileListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = NovaPoshtaSenderProfileSerializer
    pagination_class = None

    def get_queryset(self):
        return NovaPoshtaSenderProfile.objects.order_by("-is_default", "name")


class NovaPoshtaSenderProfileRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = NovaPoshtaSenderProfileSerializer
    lookup_field = "id"

    def get_queryset(self):
        return NovaPoshtaSenderProfile.objects.order_by("-is_default", "name")


class NovaPoshtaSenderProfileValidateAPIView(BackofficeAPIView):
    def post(self, request, id):
        profile = get_object_or_404(NovaPoshtaSenderProfile, id=id)
        service = NovaPoshtaSenderProfileService()

        try:
            payload = service.validate_profile(profile=profile)
        except NovaPoshtaIntegrationError as exc:
            service.mark_validation_failed(profile=profile, message=str(exc), payload=getattr(exc.context, "raw_response", {}))
            return _nova_poshta_error_response(exc)

        return Response(payload)


class NovaPoshtaSettlementsLookupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = NovaPoshtaLookupQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"])
        service = NovaPoshtaLookupService(api_token=sender.api_token)

        try:
            rows = service.search_settlements(
                query=serializer.validated_data.get("query", ""),
                locale=serializer.validated_data.get("locale", "uk"),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"results": rows})


class NovaPoshtaStreetsLookupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = NovaPoshtaStreetLookupQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"])
        service = NovaPoshtaLookupService(api_token=sender.api_token)

        try:
            rows = service.search_streets(
                settlement_ref=serializer.validated_data["settlement_ref"],
                query=serializer.validated_data.get("query", ""),
                locale=serializer.validated_data.get("locale", "uk"),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"results": rows})


class NovaPoshtaWarehousesLookupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = NovaPoshtaWarehouseLookupQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"])
        service = NovaPoshtaLookupService(api_token=sender.api_token)

        try:
            rows = service.get_warehouses(
                city_ref=serializer.validated_data["city_ref"],
                query=serializer.validated_data.get("query", ""),
                locale=serializer.validated_data.get("locale", "uk"),
                warehouse_type_ref=serializer.validated_data.get("warehouse_type_ref") or None,
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"results": rows})


class NovaPoshtaPackingsLookupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = NovaPoshtaPackListLookupQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"])
        service = NovaPoshtaLookupService(api_token=sender.api_token)

        try:
            rows = service.get_pack_list_special(
                length_mm=serializer.validated_data.get("length_mm"),
                width_mm=serializer.validated_data.get("width_mm"),
                height_mm=serializer.validated_data.get("height_mm"),
                locale=serializer.validated_data.get("locale", "uk"),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"results": rows})


class NovaPoshtaTimeIntervalsLookupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = NovaPoshtaTimeIntervalsLookupQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"])
        service = NovaPoshtaLookupService(api_token=sender.api_token)

        try:
            rows = service.get_time_intervals(
                recipient_city_ref=serializer.validated_data["recipient_city_ref"],
                date_time=serializer.validated_data.get("date_time", ""),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"results": rows})


class NovaPoshtaDeliveryDateLookupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = NovaPoshtaDeliveryDateLookupQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"])
        service = NovaPoshtaLookupService(api_token=sender.api_token)

        try:
            result = service.get_document_delivery_date(
                city_sender_ref=sender.city_ref,
                recipient_city_ref=serializer.validated_data["recipient_city_ref"],
                delivery_type=serializer.validated_data.get("delivery_type", "warehouse"),
                date_time=serializer.validated_data.get("date_time", ""),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"result": result})


class NovaPoshtaCounterpartiesLookupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = NovaPoshtaCounterpartyLookupQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"])
        service = NovaPoshtaLookupService(api_token=sender.api_token)

        try:
            rows = service.search_counterparties(
                query=serializer.validated_data.get("query", ""),
                counterparty_property=serializer.validated_data.get("counterparty_property", "Sender"),
                locale=serializer.validated_data.get("locale", "uk"),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"results": rows})


class NovaPoshtaCounterpartyDetailsLookupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = NovaPoshtaCounterpartyDetailsQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"])
        service = NovaPoshtaLookupService(api_token=sender.api_token)

        try:
            details = service.get_counterparty_details(
                counterparty_ref=serializer.validated_data["counterparty_ref"],
                counterparty_property=serializer.validated_data.get("counterparty_property", "Sender"),
                locale=serializer.validated_data.get("locale", "uk"),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"result": details})


class OrderNovaPoshtaWaybillDetailAPIView(BackofficeAPIView):
    def get(self, request, order_id):
        order = get_object_or_404(Order.objects.prefetch_related("nova_poshta_waybills", "nova_poshta_waybills__sender_profile"), id=order_id)
        service = NovaPoshtaWaybillService()
        waybill = service.get_active_waybill(order=order)

        summary = {
            "exists": bool(waybill),
            "is_deleted": bool(waybill.is_deleted) if waybill else False,
            "np_number": waybill.np_number if waybill else "",
            "status_code": waybill.status_code if waybill else "",
            "status_text": resolve_tracking_status_text(
                status_code=waybill.status_code if waybill else "",
                status_text=waybill.status_text if waybill else "",
            ),
            "has_sync_error": bool(waybill.last_sync_error) if waybill else False,
        }

        return Response(
            {
                "waybill": OrderNovaPoshtaWaybillSerializer(waybill).data if waybill else None,
                "summary": NovaPoshtaWaybillSummarySerializer(summary).data,
            }
        )


class OrderNovaPoshtaWaybillCreateAPIView(BackofficeAPIView):
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        serializer = OrderNovaPoshtaWaybillUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"], is_active=True)
        service = NovaPoshtaWaybillService()

        try:
            payload = service.build_upsert_payload(sender_profile=sender, data=serializer.validated_data)
            waybill = service.create_waybill(order=order, payload=payload, actor=request.user)
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response(OrderNovaPoshtaWaybillSerializer(waybill).data, status=status.HTTP_201_CREATED)


class OrderNovaPoshtaWaybillUpdateAPIView(BackofficeAPIView):
    def post(self, request, order_id):
        order = get_object_or_404(Order.objects.prefetch_related("nova_poshta_waybills"), id=order_id)
        serializer = OrderNovaPoshtaWaybillUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = get_object_or_404(NovaPoshtaSenderProfile, id=serializer.validated_data["sender_profile_id"], is_active=True)
        service = NovaPoshtaWaybillService()
        waybill = service.get_active_waybill(order=order)
        if not waybill:
            return Response({"detail": "ТТН не найдена для этого заказа."}, status=status.HTTP_404_NOT_FOUND)

        try:
            payload = service.build_upsert_payload(sender_profile=sender, data=serializer.validated_data)
            waybill = service.update_waybill(waybill=waybill, payload=payload, actor=request.user)
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response(OrderNovaPoshtaWaybillSerializer(waybill).data)


class OrderNovaPoshtaWaybillDeleteAPIView(BackofficeAPIView):
    def post(self, request, order_id):
        order = get_object_or_404(Order.objects.prefetch_related("nova_poshta_waybills"), id=order_id)
        service = NovaPoshtaWaybillService()
        waybill = service.get_active_waybill(order=order)
        if not waybill:
            return Response({"detail": "ТТН не найдена для этого заказа."}, status=status.HTTP_404_NOT_FOUND)

        try:
            waybill = service.delete_waybill(waybill=waybill, actor=request.user)
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response(OrderNovaPoshtaWaybillSerializer(waybill).data)


class OrderNovaPoshtaWaybillSyncAPIView(BackofficeAPIView):
    def post(self, request, order_id):
        order = get_object_or_404(Order.objects.prefetch_related("nova_poshta_waybills"), id=order_id)
        service = NovaPoshtaWaybillService()
        waybill = service.get_active_waybill(order=order)
        if not waybill:
            return Response({"detail": "ТТН не найдена для этого заказа."}, status=status.HTTP_404_NOT_FOUND)

        try:
            waybill = service.sync_waybill(waybill=waybill, actor=request.user)
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response(OrderNovaPoshtaWaybillSerializer(waybill).data)


class OrderNovaPoshtaWaybillPrintAPIView(BackofficeAPIView):
    def get(self, request, order_id):
        fmt = request.query_params.get("format", "html").strip().lower()
        if fmt not in {"html", "pdf"}:
            fmt = "html"

        order = get_object_or_404(Order.objects.prefetch_related("nova_poshta_waybills", "nova_poshta_waybills__sender_profile"), id=order_id)
        service = NovaPoshtaWaybillService()
        waybill = service.get_active_waybill(order=order)
        if not waybill:
            return Response({"detail": "ТТН не найдена для этого заказа."}, status=status.HTTP_404_NOT_FOUND)

        identifier = waybill.np_ref or waybill.np_number
        if not identifier:
            return Response({"detail": "У ТТН отсутствует идентификатор для печати."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = NovaPoshtaApiClient(api_token=waybill.sender_profile.api_token)
            body, content_type = client.download_print_form(identifier=identifier, fmt=fmt)
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        OrderNovaPoshtaWaybillEvent.objects.create(
            waybill=waybill,
            order=waybill.order,
            event_type=OrderNovaPoshtaWaybillEvent.EVENT_PRINT,
            message=f"Print requested: {fmt}",
            payload={"format": fmt},
            raw_response={},
            created_by=request.user,
        )

        filename_suffix = "html" if fmt == "html" else "pdf"
        filename = f"np-waybill-{smart_str(waybill.np_number or identifier)}.{filename_suffix}"
        response = HttpResponse(body, content_type=content_type or ("text/html" if fmt == "html" else "application/pdf"))
        disposition = "inline" if fmt == "html" else "attachment"
        response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        return response


def _nova_poshta_error_response(exc: NovaPoshtaIntegrationError) -> Response:
    context = exc.context
    return Response(
        {
            "detail": str(exc),
            "errors": context.errors,
            "warnings": context.warnings,
            "info": context.info,
            "errorCodes": context.error_codes,
            "warningCodes": context.warning_codes,
            "infoCodes": context.info_codes,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
