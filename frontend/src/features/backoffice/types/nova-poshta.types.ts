export type NovaPoshtaSenderType = "private_person" | "fop" | "business" | "organization";

export type BackofficeNovaPoshtaSenderProfile = {
  id: string;
  name: string;
  sender_type: NovaPoshtaSenderType;
  api_token_masked: string;
  counterparty_ref: string;
  contact_ref: string;
  address_ref: string;
  city_ref: string;
  phone: string;
  contact_name: string;
  organization_name: string;
  edrpou: string;
  is_active: boolean;
  is_default: boolean;
  last_validated_at: string | null;
  last_validation_ok: boolean;
  last_validation_message: string;
  last_validation_payload: Record<string, unknown>;
  raw_meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type BackofficeNovaPoshtaLookupSettlement = {
  ref: string;
  delivery_city_ref: string;
  settlement_ref: string;
  label: string;
  main_description: string;
  area: string;
  region: string;
  address_delivery_allowed: boolean;
  streets_available: boolean;
  warehouses_count: string;
  locale: string;
};

export type BackofficeNovaPoshtaLookupStreet = {
  settlement_ref: string;
  street_ref: string;
  label: string;
  street_name: string;
  street_name_ru: string;
  street_type: string;
};

export type BackofficeNovaPoshtaLookupWarehouse = {
  ref: string;
  number: string;
  city_ref: string;
  settlement_ref: string;
  type: string;
  category: string;
  label: string;
  description: string;
  full_description: string;
  post_finance: boolean;
};

export type BackofficeNovaPoshtaLookupPackaging = {
  ref: string;
  label: string;
  description: string;
  description_ru: string;
  length_mm: string;
  width_mm: string;
  height_mm: string;
  cost: string;
};

export type BackofficeNovaPoshtaLookupTimeInterval = {
  number: string;
  start: string;
  end: string;
  label: string;
};

export type BackofficeNovaPoshtaLookupDeliveryDate = {
  date: string;
  raw_datetime: string;
};

export type BackofficeNovaPoshtaLookupCounterparty = {
  ref: string;
  counterparty_ref: string;
  city_ref: string;
  city_label: string;
  label: string;
  full_name: string;
  first_name: string;
  last_name: string;
  middle_name: string;
  phone: string;
  address: string;
  ownership_form_description: string;
  edrpou: string;
  counterparty_type: string;
  locale: string;
};

export type BackofficeNovaPoshtaCounterpartyDetails = {
  contact_ref: string;
  contact_name: string;
  phone: string;
  city_ref: string;
  city_label: string;
  address_ref: string;
  address_label: string;
};

export type BackofficeOrderNovaPoshtaWaybill = {
  id: string;
  order_id: string;
  sender_profile_id: string;
  sender_profile_name: string;
  sender_profile_type: NovaPoshtaSenderType;
  np_ref: string;
  np_number: string;
  status_code: string;
  status_text: string;
  status_synced_at: string | null;
  payer_type: string;
  payment_method: string;
  service_type: string;
  cargo_type: string;
  cost: string;
  weight: string;
  seats_amount: number;
  afterpayment_amount: string | null;
  recipient_city_ref: string;
  recipient_city_label: string;
  recipient_address_ref: string;
  recipient_address_label: string;
  recipient_counterparty_ref: string;
  recipient_contact_ref: string;
  recipient_name: string;
  recipient_phone: string;
  recipient_street_ref: string;
  recipient_street_label: string;
  recipient_house: string;
  recipient_apartment: string;
  description_snapshot: string;
  additional_information_snapshot: string;
  info_reg_client_barcodes: string;
  saturday_delivery: boolean;
  local_express: boolean;
  delivery_by_hand: boolean;
  delivery_by_hand_recipients: string;
  special_cargo: boolean;
  preferred_delivery_date: string;
  time_interval: "CityDeliveryTimeInterval1" | "CityDeliveryTimeInterval2" | "CityDeliveryTimeInterval3" | "CityDeliveryTimeInterval4" | "";
  accompanying_documents: string;
  red_box_barcode: string;
  number_of_floors_lifting: string;
  number_of_floors_descent: string;
  forwarding_count: string;
  error_codes: string[];
  warning_codes: string[];
  info_codes: string[];
  can_edit: boolean;
  last_sync_error: string;
  is_deleted: boolean;
  deleted_at: string | null;
  created_by_id: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
  events_count: number;
  options_seat: BackofficeNovaPoshtaWaybillSeatOption[];
  tracking_events: BackofficeNovaPoshtaWaybillTrackingEvent[];
};

export type BackofficeNovaPoshtaWaybillSeatOption = {
  description: string;
  cost: string;
  weight: string;
  pack_ref: string;
  pack_refs: string[];
  volumetric_width: string;
  volumetric_length: string;
  volumetric_height: string;
  volumetric_volume: string;
  cargo_type: "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels";
  special_cargo: boolean;
};

export type BackofficeNovaPoshtaWaybillTrackingEvent = {
  id: string;
  event_type: string;
  status_code: string;
  status_text: string;
  location: string;
  warehouse: string;
  note: string;
  comment: string;
  event_at: string;
  synced_at: string;
};

export type BackofficeOrderNovaPoshtaWaybillSummary = {
  exists: boolean;
  is_deleted: boolean;
  np_number: string;
  status_code: string;
  status_text: string;
  has_sync_error: boolean;
};

export type BackofficeOrderNovaPoshtaWaybillResponse = {
  waybill: BackofficeOrderNovaPoshtaWaybill | null;
  summary: BackofficeOrderNovaPoshtaWaybillSummary;
};
