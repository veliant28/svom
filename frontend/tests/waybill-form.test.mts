import assert from "node:assert/strict";
import test from "node:test";

import {
  buildWaybillInitialPayload,
  canSaveWaybill,
  normalizeWaybillPhone,
} from "../src/features/backoffice/lib/orders/waybill-form.ts";

test("normalizeWaybillPhone strips spaces", () => {
  assert.equal(normalizeWaybillPhone(" +380 67 123 45 67 "), "+380671234567");
});

test("buildWaybillInitialPayload uses order defaults", () => {
  const payload = buildWaybillInitialPayload(
    {
      id: "o1",
      order_number: "ORD-1",
      status: "new",
      user_id: "u1",
      user_email: "user@test.local",
      contact_full_name: "John Smith",
      contact_phone: "+380671234567",
      contact_email: "john@test.local",
      delivery_method: "nova_poshta",
      payment_method: "cash_on_delivery",
      subtotal: "100.00",
      delivery_fee: "0.00",
      total: "100.00",
      currency: "UAH",
      items_count: 2,
      issues_count: 0,
      nova_poshta_waybill_exists: false,
      nova_poshta_waybill_number: "",
      nova_poshta_waybill_status_code: "",
      nova_poshta_waybill_status_text: "",
      nova_poshta_waybill_has_error: false,
      placed_at: "",
    },
    null,
    "sender-1",
  );

  assert.equal(payload.sender_profile_id, "sender-1");
  assert.equal(payload.recipient_name, "John Smith");
  assert.equal(payload.cost, "100.00");
});

test("canSaveWaybill validates required fields for warehouse", () => {
  assert.equal(canSaveWaybill({
    sender_profile_id: "sender-1",
    delivery_type: "warehouse",
    recipient_city_ref: "city-ref",
    recipient_name: "John",
    recipient_phone: "+380671234567",
    recipient_address_ref: "warehouse-ref",
    weight: "1.0",
    cost: "100",
  }), true);

  assert.equal(canSaveWaybill({
    sender_profile_id: "sender-1",
    delivery_type: "warehouse",
    recipient_city_ref: "city-ref",
    recipient_name: "John",
    recipient_phone: "+380671234567",
    recipient_address_ref: "",
    weight: "1.0",
    cost: "100",
  }), false);
});

test("canSaveWaybill validates required fields for address", () => {
  assert.equal(canSaveWaybill({
    sender_profile_id: "sender-1",
    delivery_type: "address",
    recipient_city_ref: "city-ref",
    recipient_name: "John",
    recipient_phone: "+380671234567",
    recipient_street_ref: "street-ref",
    recipient_house: "10",
    weight: "1.0",
    cost: "100",
  }), true);

  assert.equal(canSaveWaybill({
    sender_profile_id: "sender-1",
    delivery_type: "address",
    recipient_city_ref: "city-ref",
    recipient_name: "John",
    recipient_phone: "+380671234567",
    recipient_street_ref: "",
    recipient_house: "",
    weight: "1.0",
    cost: "100",
  }), false);
});
