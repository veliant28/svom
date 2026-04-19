import { postJson } from "@/shared/api/http-client";

export type CheckoutNovaPoshtaSettlement = {
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

export type CheckoutNovaPoshtaWarehouse = {
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

export type CheckoutNovaPoshtaStreet = {
  settlement_ref: string;
  street_ref: string;
  label: string;
  street_name: string;
  street_name_ru: string;
  street_type: string;
};

export async function lookupCheckoutNovaPoshtaSettlements(
  token: string,
  payload: { query: string; locale?: string },
): Promise<{ results: CheckoutNovaPoshtaSettlement[] }> {
  return postJson<{ results: CheckoutNovaPoshtaSettlement[] }, typeof payload>(
    "/commerce/checkout/lookups/nova-poshta/settlements/",
    payload,
    undefined,
    { token },
  );
}

export async function lookupCheckoutNovaPoshtaWarehouses(
  token: string,
  payload: { city_ref: string; query: string; locale?: string },
): Promise<{ results: CheckoutNovaPoshtaWarehouse[] }> {
  return postJson<{ results: CheckoutNovaPoshtaWarehouse[] }, typeof payload>(
    "/commerce/checkout/lookups/nova-poshta/warehouses/",
    payload,
    undefined,
    { token },
  );
}

export async function lookupCheckoutNovaPoshtaStreets(
  token: string,
  payload: { settlement_ref: string; query: string; locale?: string },
): Promise<{ results: CheckoutNovaPoshtaStreet[] }> {
  return postJson<{ results: CheckoutNovaPoshtaStreet[] }, typeof payload>(
    "/commerce/checkout/lookups/nova-poshta/streets/",
    payload,
    undefined,
    { token },
  );
}
