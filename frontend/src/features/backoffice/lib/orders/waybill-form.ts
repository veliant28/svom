import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";
import type { BackofficeOrderNovaPoshtaWaybill } from "@/features/backoffice/types/nova-poshta.types";

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
};

export function normalizeWaybillPhone(value: string): string {
  return value.replace(/\s+/g, "").trim();
}

export function buildWaybillInitialPayload(
  order: BackofficeOrderOperational | null,
  waybill: BackofficeOrderNovaPoshtaWaybill | null,
  senderId: string,
): WaybillFormPayload {
  if (waybill) {
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
      saturday_delivery: false,
      local_express: false,
      preferred_delivery_date: "",
      time_interval: "",
      info_reg_client_barcodes: "",
      accompanying_documents: "",
      red_box_barcode: "",
      number_of_floors_lifting: "",
      number_of_floors_descent: "",
      forwarding_count: "",
      delivery_by_hand: false,
      delivery_by_hand_recipients: "",
      special_cargo: false,
    };
  }

  return {
    sender_profile_id: senderId,
    delivery_type: "warehouse",
    payer_type: "Recipient",
    payment_method: "Cash",
    cargo_type: "Parcel",
    description: "",
    recipient_city_ref: "",
    recipient_city_label: "",
    recipient_address_ref: "",
    recipient_address_label: "",
    recipient_counterparty_ref: "",
    recipient_contact_ref: "",
    recipient_street_ref: "",
    recipient_street_label: "",
    recipient_house: "",
    recipient_apartment: "",
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
    info_reg_client_barcodes: "",
    accompanying_documents: "",
    red_box_barcode: "",
    number_of_floors_lifting: "",
    number_of_floors_descent: "",
    forwarding_count: "",
    delivery_by_hand: false,
    delivery_by_hand_recipients: "",
    special_cargo: false,
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
