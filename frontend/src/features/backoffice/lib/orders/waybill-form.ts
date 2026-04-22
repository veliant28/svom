import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";
import type { BackofficeOrderNovaPoshtaWaybill } from "@/features/backoffice/types/nova-poshta.types";

export type WaybillSeatOptionPayload = {
  description?: string;
  cost?: string;
  weight?: string;
  pack_ref?: string;
  pack_refs?: string[];
  volumetric_width?: string;
  volumetric_length?: string;
  volumetric_height?: string;
  volumetric_volume?: string;
  cargo_type?: "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels";
  special_cargo?: boolean;
};

export type WaybillFormPayload = {
  sender_profile_id: string;
  delivery_type: "warehouse" | "postomat" | "address";
  payer_type?: "Sender" | "Recipient" | "ThirdPerson";
  payment_method?: "Cash" | "NonCash";
  cargo_type?: "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels";
  description?: string;
  recipient_city_ref: string;
  recipient_city_label?: string;
  recipient_address_ref?: string;
  recipient_address_label?: string;
  recipient_counterparty_ref?: string;
  recipient_contact_ref?: string;
  recipient_street_ref?: string;
  recipient_street_label?: string;
  recipient_house?: string;
  recipient_apartment?: string;
  recipient_name: string;
  recipient_phone: string;
  seats_amount?: number;
  weight: string;
  volume_general?: string;
  pack_ref?: string;
  pack_refs?: string[];
  volumetric_width?: string;
  volumetric_length?: string;
  volumetric_height?: string;
  cost: string;
  afterpayment_amount?: string;
  saturday_delivery?: boolean;
  local_express?: boolean;
  preferred_delivery_date?: string;
  time_interval?: "CityDeliveryTimeInterval1" | "CityDeliveryTimeInterval2" | "CityDeliveryTimeInterval3" | "CityDeliveryTimeInterval4" | "";
  info_reg_client_barcodes?: string;
  accompanying_documents?: string;
  red_box_barcode?: string;
  number_of_floors_lifting?: string;
  number_of_floors_descent?: string;
  forwarding_count?: string;
  delivery_by_hand?: boolean;
  delivery_by_hand_recipients?: string;
  special_cargo?: boolean;
  options_seat?: WaybillSeatOptionPayload[];
};

export function normalizeWaybillPhone(value: string): string {
  return value.replace(/\s+/g, "").trim();
}

export function buildWaybillInitialPayload(
  order: BackofficeOrderOperational | null,
  waybill: BackofficeOrderNovaPoshtaWaybill | null,
  senderId: string,
): WaybillFormPayload {
  const buildDefaultSeat = (
    values: {
      description?: string;
      cost?: string;
      weight?: string;
      cargo_type?: "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels";
      special_cargo?: boolean;
    },
  ): WaybillSeatOptionPayload => ({
    description: values.description || "",
    cost: values.cost || "0",
    weight: values.weight || "0.001",
    pack_ref: "",
    pack_refs: [],
    volumetric_width: "",
    volumetric_length: "",
    volumetric_height: "",
    volumetric_volume: "",
    cargo_type: values.cargo_type || "Parcel",
    special_cargo: Boolean(values.special_cargo),
  });

  const normalizeSeat = (
    seat: BackofficeOrderNovaPoshtaWaybill["options_seat"][number] | null | undefined,
    fallback: WaybillSeatOptionPayload,
  ): WaybillSeatOptionPayload => {
    if (!seat) {
      return fallback;
    }
    const refs = Array.isArray(seat.pack_refs)
      ? seat.pack_refs.map((item) => String(item || "").trim()).filter(Boolean)
      : ((seat.pack_ref || "").trim() ? [(seat.pack_ref || "").trim()] : []);
    return {
      description: (seat.description || "").trim() || fallback.description || "",
      cost: (seat.cost || "").trim() || fallback.cost || "0",
      weight: (seat.weight || "").trim() || fallback.weight || "0.001",
      pack_ref: refs[0] || "",
      pack_refs: refs,
      volumetric_width: (seat.volumetric_width || "").trim(),
      volumetric_length: (seat.volumetric_length || "").trim(),
      volumetric_height: (seat.volumetric_height || "").trim(),
      volumetric_volume: (seat.volumetric_volume || "").trim(),
      cargo_type: seat.cargo_type || fallback.cargo_type || "Parcel",
      special_cargo: seat.special_cargo ?? fallback.special_cargo ?? false,
    };
  };

  if (waybill) {
    const fallbackSeat = buildDefaultSeat({
      description: waybill.description_snapshot,
      cost: waybill.cost,
      weight: waybill.weight,
      cargo_type: (waybill.cargo_type as "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels") || "Parcel",
      special_cargo: false,
    });
    const sourceSeats = Array.isArray(waybill.options_seat) ? waybill.options_seat : [];
    const seatCount = Math.max(1, waybill.seats_amount || sourceSeats.length || 1);
    const optionsSeat = sourceSeats.length
      ? sourceSeats.map((seat) => normalizeSeat(seat, fallbackSeat))
      : Array.from({ length: seatCount }, () => ({ ...fallbackSeat }));

    return {
      sender_profile_id: waybill.sender_profile_id,
      delivery_type: waybill.service_type === "WarehouseDoors" ? "address" : "warehouse",
      payer_type: (waybill.payer_type as "Sender" | "Recipient" | "ThirdPerson") || "Recipient",
      payment_method: (waybill.payment_method as "Cash" | "NonCash") || "Cash",
      cargo_type: (waybill.cargo_type as "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels") || "Parcel",
      description: waybill.description_snapshot,
      recipient_city_ref: waybill.recipient_city_ref,
      recipient_city_label: waybill.recipient_city_label,
      recipient_address_ref: waybill.recipient_address_ref,
      recipient_address_label: waybill.recipient_address_label,
      recipient_counterparty_ref: waybill.recipient_counterparty_ref,
      recipient_contact_ref: waybill.recipient_contact_ref,
      recipient_street_ref: waybill.recipient_street_ref,
      recipient_street_label: waybill.recipient_street_label,
      recipient_house: waybill.recipient_house,
      recipient_apartment: waybill.recipient_apartment,
      recipient_name: waybill.recipient_name,
      recipient_phone: waybill.recipient_phone,
      seats_amount: waybill.seats_amount,
      weight: waybill.weight,
      pack_ref: "",
      pack_refs: [],
      volumetric_width: "",
      volumetric_length: "",
      volumetric_height: "",
      cost: waybill.cost,
      afterpayment_amount: waybill.afterpayment_amount ?? "",
      saturday_delivery: Boolean(waybill.saturday_delivery),
      local_express: Boolean(waybill.local_express),
      preferred_delivery_date: waybill.preferred_delivery_date || "",
      time_interval: waybill.time_interval || "",
      info_reg_client_barcodes: waybill.info_reg_client_barcodes || order?.order_number || "",
      accompanying_documents: waybill.accompanying_documents || "",
      red_box_barcode: waybill.red_box_barcode || "",
      number_of_floors_lifting: waybill.number_of_floors_lifting || "",
      number_of_floors_descent: waybill.number_of_floors_descent || "",
      forwarding_count: waybill.forwarding_count || "",
      delivery_by_hand: Boolean(waybill.delivery_by_hand),
      delivery_by_hand_recipients: waybill.delivery_by_hand_recipients || "",
      special_cargo: Boolean(waybill.special_cargo),
      options_seat: optionsSeat,
    };
  }

  const seed = order?.delivery_waybill_seed;
  const seedDeliveryType = seed?.delivery_type;
  const normalizedSeedDeliveryType: "warehouse" | "postomat" | "address" = seedDeliveryType === "address"
    ? "address"
    : seedDeliveryType === "postomat"
      ? "postomat"
      : "warehouse";

  const defaultSeat = buildDefaultSeat({
    description: "",
    cost: order?.total ?? "0",
    weight: "1.000",
    cargo_type: "Parcel",
    special_cargo: false,
  });

  return {
    sender_profile_id: senderId,
    delivery_type: normalizedSeedDeliveryType,
    payer_type: "Recipient",
    payment_method: "Cash",
    cargo_type: "Parcel",
    description: "",
    recipient_city_ref: seed?.recipient_city_ref || "",
    recipient_city_label: seed?.recipient_city_label || order?.delivery_city_label || "",
    recipient_address_ref: seed?.recipient_address_ref || "",
    recipient_address_label: seed?.recipient_address_label || order?.delivery_destination_label || "",
    recipient_counterparty_ref: "",
    recipient_contact_ref: "",
    recipient_street_ref: seed?.recipient_street_ref || "",
    recipient_street_label: seed?.recipient_street_label || "",
    recipient_house: seed?.recipient_house || "",
    recipient_apartment: seed?.recipient_apartment || "",
    recipient_name: order?.contact_full_name ?? "",
    recipient_phone: order?.contact_phone ?? "",
    seats_amount: Math.max(1, order?.items_count ?? 1),
    weight: "1.000",
    pack_ref: "",
    pack_refs: [],
    volumetric_width: "",
    volumetric_length: "",
    volumetric_height: "",
    cost: order?.total ?? "0",
    afterpayment_amount: order?.total ?? "0",
    saturday_delivery: false,
    local_express: false,
    preferred_delivery_date: "",
    time_interval: "",
    info_reg_client_barcodes: order?.order_number ?? "",
    accompanying_documents: "",
    red_box_barcode: "",
    number_of_floors_lifting: "",
    number_of_floors_descent: "",
    forwarding_count: "",
    delivery_by_hand: false,
    delivery_by_hand_recipients: "",
    special_cargo: false,
    options_seat: [defaultSeat],
  };
}

export function canSaveWaybill(payload: WaybillFormPayload): boolean {
  if (!payload.sender_profile_id || !payload.recipient_city_ref || !payload.recipient_name || !payload.recipient_phone) {
    return false;
  }

  if (payload.delivery_type === "address") {
    return Boolean(payload.recipient_street_ref && payload.recipient_house);
  }

  return Boolean(payload.recipient_address_ref);
}
