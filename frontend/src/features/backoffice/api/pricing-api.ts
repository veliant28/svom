import { getJson, postJson } from "@/shared/api/http-client";

import type { BackofficePricingCategoryImpact, BackofficePricingControlPanel } from "@/features/backoffice/types/backoffice";

export async function getBackofficePricingControlPanel(token: string): Promise<BackofficePricingControlPanel> {
  return getJson<BackofficePricingControlPanel>("/backoffice/pricing/control-panel/", undefined, { token });
}

export async function getBackofficePricingCategoryImpact(
  token: string,
  params: { category_id: string; include_children?: boolean },
): Promise<BackofficePricingCategoryImpact> {
  return getJson<BackofficePricingCategoryImpact>("/backoffice/pricing/category-impact/", params, { token });
}

export async function updateBackofficePricingGlobalMarkup(
  token: string,
  payload: { percent_markup: number; dispatch_async?: boolean },
): Promise<{
  mode: "sync" | "async";
  affected_products: number;
  created_policies: number;
  updated_policies: number;
  markup_percent: string;
}> {
  return postJson<
  {
    mode: "sync" | "async";
    affected_products: number;
    created_policies: number;
    updated_policies: number;
    markup_percent: string;
  },
  typeof payload
  >("/backoffice/pricing/global-markup/", payload, undefined, { token });
}

export async function updateBackofficePricingCategoryMarkup(
  token: string,
  payload: { category_id: string; percent_markup: number; include_children?: boolean; dispatch_async?: boolean },
): Promise<{
  mode: "sync" | "async";
  affected_products: number;
  target_categories: number;
  created_policies: number;
  updated_policies: number;
  markup_percent: string;
}> {
  return postJson<
  {
    mode: "sync" | "async";
    affected_products: number;
    target_categories: number;
    created_policies: number;
    updated_policies: number;
    markup_percent: string;
  },
  typeof payload
  >("/backoffice/pricing/category-markup/", payload, undefined, { token });
}

export async function runBackofficePricingRecalculate(
  token: string,
  payload: { dispatch_async?: boolean; category_id?: string; include_children?: boolean },
): Promise<{ mode: "sync" | "async"; affected_products: number; target_categories: number }> {
  return postJson<{ mode: "sync" | "async"; affected_products: number; target_categories: number }, typeof payload>(
    "/backoffice/pricing/recalculate/",
    payload,
    undefined,
    { token },
  );
}
