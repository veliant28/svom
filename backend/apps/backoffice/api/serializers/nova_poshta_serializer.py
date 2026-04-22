from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.commerce.models import NovaPoshtaSenderProfile, OrderNovaPoshtaWaybill, OrderNovaPoshtaWaybillEvent
from apps.commerce.services.nova_poshta.tracking_status_catalog import resolve_tracking_status_text


class NovaPoshtaSenderProfileSerializer(serializers.ModelSerializer):
    api_token = serializers.CharField(write_only=True, required=False, allow_blank=False, trim_whitespace=True)
    api_token_masked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = NovaPoshtaSenderProfile
        fields = (
            "id",
            "name",
            "sender_type",
            "api_token",
            "api_token_masked",
            "counterparty_ref",
            "contact_ref",
            "address_ref",
            "city_ref",
            "phone",
            "contact_name",
            "organization_name",
            "edrpou",
            "is_active",
            "is_default",
            "last_validated_at",
            "last_validation_ok",
            "last_validation_message",
            "last_validation_payload",
            "raw_meta",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "api_token_masked",
            "last_validated_at",
            "last_validation_ok",
            "last_validation_message",
            "last_validation_payload",
            "created_at",
            "updated_at",
        )

    def get_api_token_masked(self, obj: NovaPoshtaSenderProfile) -> str:
        token = (obj.api_token or "").strip()
        if not token:
            return ""
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}...{token[-4:]}"

    def validate(self, attrs):
        attrs = super().validate(attrs)

        instance: NovaPoshtaSenderProfile | None = getattr(self, "instance", None)
        token = attrs.get("api_token")
        if instance is None and not token:
            raise serializers.ValidationError({"api_token": "Это поле обязательно."})

        return attrs

    def create(self, validated_data):
        is_default = bool(validated_data.get("is_default"))
        instance = super().create(validated_data)
        if is_default:
            NovaPoshtaSenderProfile.objects.exclude(id=instance.id).filter(is_default=True).update(is_default=False)
        return instance

    def update(self, instance, validated_data):
        is_default = validated_data.get("is_default")
        instance = super().update(instance, validated_data)
        if is_default:
            NovaPoshtaSenderProfile.objects.exclude(id=instance.id).filter(is_default=True).update(is_default=False)
        return instance


class NovaPoshtaLookupQuerySerializer(serializers.Serializer):
    sender_profile_id = serializers.UUIDField()
    query = serializers.CharField(required=False, allow_blank=True, default="")
    locale = serializers.CharField(required=False, allow_blank=True, default="uk")


class NovaPoshtaStreetLookupQuerySerializer(NovaPoshtaLookupQuerySerializer):
    settlement_ref = serializers.CharField()


class NovaPoshtaWarehouseLookupQuerySerializer(NovaPoshtaLookupQuerySerializer):
    city_ref = serializers.CharField(required=False, allow_blank=True, default="")
    warehouse_type_ref = serializers.CharField(required=False, allow_blank=True)


class NovaPoshtaCounterpartyLookupQuerySerializer(NovaPoshtaLookupQuerySerializer):
    counterparty_property = serializers.CharField(required=False, allow_blank=True, default="Sender")


class NovaPoshtaCounterpartyDetailsQuerySerializer(NovaPoshtaLookupQuerySerializer):
    counterparty_ref = serializers.CharField()
    counterparty_property = serializers.CharField(required=False, allow_blank=True, default="Sender")


class NovaPoshtaPackListLookupQuerySerializer(NovaPoshtaLookupQuerySerializer):
    length_mm = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5000)
    width_mm = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5000)
    height_mm = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5000)


class NovaPoshtaTimeIntervalsLookupQuerySerializer(NovaPoshtaLookupQuerySerializer):
    recipient_city_ref = serializers.CharField()
    date_time = serializers.CharField(required=False, allow_blank=True, default="")


class NovaPoshtaDeliveryDateLookupQuerySerializer(NovaPoshtaLookupQuerySerializer):
    recipient_city_ref = serializers.CharField()
    delivery_type = serializers.ChoiceField(choices=["warehouse", "postomat", "address"], default="warehouse")
    date_time = serializers.CharField(required=False, allow_blank=True, default="")


class OrderNovaPoshtaWaybillSeatOptionSerializer(serializers.Serializer):
    description = serializers.CharField(required=False, allow_blank=True, default="")
    cost = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0, allow_null=True)
    weight = serializers.DecimalField(required=False, max_digits=10, decimal_places=3, min_value=Decimal("0.001"), allow_null=True)
    pack_ref = serializers.CharField(required=False, allow_blank=True, default="")
    pack_refs = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        default=list,
    )
    volumetric_width = serializers.DecimalField(required=False, max_digits=10, decimal_places=3, min_value=Decimal("0.001"), allow_null=True)
    volumetric_length = serializers.DecimalField(required=False, max_digits=10, decimal_places=3, min_value=Decimal("0.001"), allow_null=True)
    volumetric_height = serializers.DecimalField(required=False, max_digits=10, decimal_places=3, min_value=Decimal("0.001"), allow_null=True)
    volumetric_volume = serializers.DecimalField(required=False, max_digits=10, decimal_places=4, min_value=Decimal("0.0001"), allow_null=True)
    cargo_type = serializers.ChoiceField(
        choices=["Cargo", "Parcel", "Documents", "Pallet", "TiresWheels"],
        required=False,
        default="Parcel",
    )
    special_cargo = serializers.BooleanField(required=False, default=False)


class OrderNovaPoshtaWaybillUpsertSerializer(serializers.Serializer):
    sender_profile_id = serializers.UUIDField()
    delivery_type = serializers.ChoiceField(choices=["warehouse", "postomat", "address"], default="warehouse")
    payer_type = serializers.ChoiceField(choices=["Sender", "Recipient", "ThirdPerson"], required=False, allow_null=True)
    payment_method = serializers.ChoiceField(choices=["Cash", "NonCash"], required=False, allow_null=True)
    cargo_type = serializers.ChoiceField(
        choices=["Cargo", "Parcel", "Documents", "Pallet", "TiresWheels"],
        required=False,
        default="Parcel",
    )
    description = serializers.CharField(required=False, allow_blank=True, default="")

    recipient_city_ref = serializers.CharField()
    recipient_city_label = serializers.CharField(required=False, allow_blank=True, default="")
    recipient_address_ref = serializers.CharField(required=False, allow_blank=True, default="")
    recipient_address_label = serializers.CharField(required=False, allow_blank=True, default="")
    recipient_counterparty_ref = serializers.CharField(required=False, allow_blank=True, default="")
    recipient_contact_ref = serializers.CharField(required=False, allow_blank=True, default="")

    recipient_street_ref = serializers.CharField(required=False, allow_blank=True, default="")
    recipient_street_label = serializers.CharField(required=False, allow_blank=True, default="")
    recipient_house = serializers.CharField(required=False, allow_blank=True, default="")
    recipient_apartment = serializers.CharField(required=False, allow_blank=True, default="")

    recipient_name = serializers.CharField()
    recipient_phone = serializers.CharField()

    seats_amount = serializers.IntegerField(required=False, min_value=1, default=1)
    weight = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal("0.001"))
    volume_general = serializers.DecimalField(required=False, max_digits=10, decimal_places=4, min_value=Decimal("0.0001"))
    pack_ref = serializers.CharField(required=False, allow_blank=True, default="")
    pack_refs = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        default=list,
    )
    volumetric_width = serializers.DecimalField(required=False, max_digits=10, decimal_places=3, min_value=Decimal("0.001"))
    volumetric_length = serializers.DecimalField(required=False, max_digits=10, decimal_places=3, min_value=Decimal("0.001"))
    volumetric_height = serializers.DecimalField(required=False, max_digits=10, decimal_places=3, min_value=Decimal("0.001"))
    cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    afterpayment_amount = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0)
    saturday_delivery = serializers.BooleanField(required=False, default=False)
    local_express = serializers.BooleanField(required=False, default=False)
    preferred_delivery_date = serializers.CharField(required=False, allow_blank=True, default="")
    time_interval = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        choices=[
            "",
            "CityDeliveryTimeInterval1",
            "CityDeliveryTimeInterval2",
            "CityDeliveryTimeInterval3",
            "CityDeliveryTimeInterval4",
        ],
        default="",
    )
    info_reg_client_barcodes = serializers.CharField(required=False, allow_blank=True, default="")
    accompanying_documents = serializers.CharField(required=False, allow_blank=True, default="")
    red_box_barcode = serializers.CharField(required=False, allow_blank=True, default="")
    number_of_floors_lifting = serializers.CharField(required=False, allow_blank=True, default="")
    number_of_floors_descent = serializers.CharField(required=False, allow_blank=True, default="")
    forwarding_count = serializers.CharField(required=False, allow_blank=True, default="")
    delivery_by_hand = serializers.BooleanField(required=False, default=False)
    delivery_by_hand_recipients = serializers.CharField(required=False, allow_blank=True, default="")
    special_cargo = serializers.BooleanField(required=False, default=False)
    options_seat = OrderNovaPoshtaWaybillSeatOptionSerializer(many=True, required=False, allow_empty=True, default=list)


class OrderNovaPoshtaWaybillSerializer(serializers.ModelSerializer):
    sender_profile_name = serializers.CharField(source="sender_profile.name", read_only=True)
    sender_profile_type = serializers.CharField(source="sender_profile.sender_type", read_only=True)
    events_count = serializers.SerializerMethodField(read_only=True)
    status_text = serializers.SerializerMethodField(read_only=True)
    options_seat = serializers.SerializerMethodField(read_only=True)
    tracking_events = serializers.SerializerMethodField(read_only=True)
    info_reg_client_barcodes = serializers.SerializerMethodField(read_only=True)
    saturday_delivery = serializers.SerializerMethodField(read_only=True)
    local_express = serializers.SerializerMethodField(read_only=True)
    delivery_by_hand = serializers.SerializerMethodField(read_only=True)
    delivery_by_hand_recipients = serializers.SerializerMethodField(read_only=True)
    special_cargo = serializers.SerializerMethodField(read_only=True)
    preferred_delivery_date = serializers.SerializerMethodField(read_only=True)
    time_interval = serializers.SerializerMethodField(read_only=True)
    accompanying_documents = serializers.SerializerMethodField(read_only=True)
    red_box_barcode = serializers.SerializerMethodField(read_only=True)
    number_of_floors_lifting = serializers.SerializerMethodField(read_only=True)
    number_of_floors_descent = serializers.SerializerMethodField(read_only=True)
    forwarding_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OrderNovaPoshtaWaybill
        fields = (
            "id",
            "order_id",
            "sender_profile_id",
            "sender_profile_name",
            "sender_profile_type",
            "np_ref",
            "np_number",
            "status_code",
            "status_text",
            "status_synced_at",
            "payer_type",
            "payment_method",
            "service_type",
            "cargo_type",
            "cost",
            "weight",
            "seats_amount",
            "afterpayment_amount",
            "recipient_city_ref",
            "recipient_city_label",
            "recipient_address_ref",
            "recipient_address_label",
            "recipient_counterparty_ref",
            "recipient_contact_ref",
            "recipient_name",
            "recipient_phone",
            "recipient_street_ref",
            "recipient_street_label",
            "recipient_house",
            "recipient_apartment",
            "description_snapshot",
            "additional_information_snapshot",
            "info_reg_client_barcodes",
            "saturday_delivery",
            "local_express",
            "delivery_by_hand",
            "delivery_by_hand_recipients",
            "special_cargo",
            "preferred_delivery_date",
            "time_interval",
            "accompanying_documents",
            "red_box_barcode",
            "number_of_floors_lifting",
            "number_of_floors_descent",
            "forwarding_count",
            "error_codes",
            "warning_codes",
            "info_codes",
            "can_edit",
            "last_sync_error",
            "is_deleted",
            "deleted_at",
            "created_by_id",
            "updated_by_id",
            "created_at",
            "updated_at",
            "events_count",
            "options_seat",
            "tracking_events",
        )
        read_only_fields = fields

    def get_events_count(self, obj: OrderNovaPoshtaWaybill) -> int:
        return obj.events.count()

    def get_status_text(self, obj: OrderNovaPoshtaWaybill) -> str:
        return resolve_tracking_status_text(
            status_code=obj.status_code,
            status_text=obj.status_text,
        )

    def get_options_seat(self, obj: OrderNovaPoshtaWaybill) -> list[dict]:
        raw = obj.raw_request_json if isinstance(obj.raw_request_json, dict) else {}
        options = raw.get("OptionsSeat")
        if not isinstance(options, list):
            return []

        normalized: list[dict] = []
        for item in options:
            if not isinstance(item, dict):
                continue
            pack_ref = str(item.get("packRef") or "").strip()
            pack_refs = [pack_ref] if pack_ref else []
            normalized.append(
                {
                    "description": str(item.get("description") or "").strip(),
                    "cost": str(item.get("cost") or "").strip(),
                    "weight": str(item.get("weight") or "").strip(),
                    "pack_ref": pack_ref,
                    "pack_refs": pack_refs,
                    "volumetric_width": str(item.get("volumetricWidth") or "").strip(),
                    "volumetric_length": str(item.get("volumetricLength") or "").strip(),
                    "volumetric_height": str(item.get("volumetricHeight") or "").strip(),
                    "volumetric_volume": str(item.get("volumetricVolume") or "").strip(),
                    "cargo_type": str(item.get("cargoType") or "").strip() or "Parcel",
                    "special_cargo": str(item.get("specialCargo") or "").strip() in {"1", "true", "True"},
                }
            )
        return normalized

    def get_info_reg_client_barcodes(self, obj: OrderNovaPoshtaWaybill) -> str:
        raw = self._raw_request(obj)
        return str(raw.get("InfoRegClientBarcodes") or "").strip()

    def get_saturday_delivery(self, obj: OrderNovaPoshtaWaybill) -> bool:
        return self._parse_np_bool(self._raw_request(obj).get("SaturdayDelivery"))

    def get_local_express(self, obj: OrderNovaPoshtaWaybill) -> bool:
        return self._parse_np_bool(self._raw_request(obj).get("LocalExpress"))

    def get_delivery_by_hand(self, obj: OrderNovaPoshtaWaybill) -> bool:
        return self._parse_np_bool(self._raw_request(obj).get("DeliveryByHand"))

    def get_delivery_by_hand_recipients(self, obj: OrderNovaPoshtaWaybill) -> str:
        value = self._raw_request(obj).get("DeliveryByHandRecipients")
        if isinstance(value, list):
            rows = [str(item).strip() for item in value if str(item).strip()]
            return "\n".join(rows)
        return str(value or "").strip()

    def get_special_cargo(self, obj: OrderNovaPoshtaWaybill) -> bool:
        raw = self._raw_request(obj)
        if self._parse_np_bool(raw.get("specialCargo")):
            return True
        options = raw.get("OptionsSeat")
        if isinstance(options, list):
            for item in options:
                if isinstance(item, dict) and self._parse_np_bool(item.get("specialCargo")):
                    return True
        return False

    def get_preferred_delivery_date(self, obj: OrderNovaPoshtaWaybill) -> str:
        return str(self._raw_request(obj).get("PreferredDeliveryDate") or "").strip()

    def get_time_interval(self, obj: OrderNovaPoshtaWaybill) -> str:
        return str(self._raw_request(obj).get("TimeInterval") or "").strip()

    def get_accompanying_documents(self, obj: OrderNovaPoshtaWaybill) -> str:
        return str(self._raw_request(obj).get("AccompanyingDocuments") or "").strip()

    def get_red_box_barcode(self, obj: OrderNovaPoshtaWaybill) -> str:
        return str(self._raw_request(obj).get("RedBoxBarcode") or "").strip()

    def get_number_of_floors_lifting(self, obj: OrderNovaPoshtaWaybill) -> str:
        return str(self._raw_request(obj).get("NumberOfFloorsLifting") or "").strip()

    def get_number_of_floors_descent(self, obj: OrderNovaPoshtaWaybill) -> str:
        return str(self._raw_request(obj).get("NumberOfFloorsDescent") or "").strip()

    def get_forwarding_count(self, obj: OrderNovaPoshtaWaybill) -> str:
        return str(self._raw_request(obj).get("ForwardingCount") or "").strip()

    @staticmethod
    def _raw_request(obj: OrderNovaPoshtaWaybill) -> dict:
        return obj.raw_request_json if isinstance(obj.raw_request_json, dict) else {}

    @staticmethod
    def _parse_np_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value or "").strip().lower()
        return normalized in {"1", "true", "yes", "y"}

    @staticmethod
    def _extract_tracking_status_data(event: OrderNovaPoshtaWaybillEvent) -> dict:
        payload = event.payload if isinstance(event.payload, dict) else {}
        status_data = payload.get("status")
        if isinstance(status_data, dict):
            return status_data

        raw_response = event.raw_response if isinstance(event.raw_response, dict) else {}
        raw_data = raw_response.get("data")
        if isinstance(raw_data, list) and raw_data and isinstance(raw_data[0], dict):
            return raw_data[0]
        return {}

    def get_tracking_events(self, obj: OrderNovaPoshtaWaybill) -> list[dict]:
        events = list(
            obj.events.filter(
                event_type=OrderNovaPoshtaWaybillEvent.EVENT_SYNC,
            )
            .exclude(status_code="")
            .order_by("-created_at")
        )
        if not events:
            events = list(obj.events.exclude(status_code="").order_by("-created_at"))
        result: list[dict] = []
        seen_snapshots: set[str] = set()
        for event in events:
            status_data = self._extract_tracking_status_data(event)
            location = str(
                status_data.get("CityRecipient")
                or status_data.get("RecipientAddress")
                or ""
            ).strip()
            warehouse = str(
                status_data.get("WarehouseRecipient")
                or status_data.get("WarehouseRecipientAddress")
                or ""
            ).strip()
            note = str(
                status_data.get("UndeliveryReasonsSubtypeDescription")
                or status_data.get("UndeliveryReasons")
                or ""
            ).strip()
            comment = str(status_data.get("CounterpartyRecipientDescription") or "").strip()
            event_at = (
                str(status_data.get("DateScan") or "").strip()
                or str(status_data.get("TrackingUpdateDate") or "").strip()
                or event.created_at.isoformat()
            )
            resolved_status_text = resolve_tracking_status_text(
                status_code=event.status_code,
                status_text=event.status_text,
            )
            snapshot_key = "|".join(
                (
                    str(event.status_code or "").strip(),
                    resolved_status_text.strip(),
                    location,
                    warehouse,
                    note,
                    comment,
                )
            ).lower()
            if snapshot_key in seen_snapshots:
                continue
            seen_snapshots.add(snapshot_key)
            result.append(
                {
                    "id": str(event.id),
                    "event_type": event.event_type,
                    "status_code": event.status_code,
                    "status_text": resolved_status_text,
                    "location": location,
                    "warehouse": warehouse,
                    "note": note,
                    "comment": comment,
                    "event_at": event_at,
                    "synced_at": event.created_at.isoformat(),
                }
            )
        return result


class NovaPoshtaWaybillSummarySerializer(serializers.Serializer):
    exists = serializers.BooleanField()
    is_deleted = serializers.BooleanField()
    np_number = serializers.CharField(allow_blank=True)
    status_code = serializers.CharField(allow_blank=True)
    status_text = serializers.CharField(allow_blank=True)
    has_sync_error = serializers.BooleanField()
