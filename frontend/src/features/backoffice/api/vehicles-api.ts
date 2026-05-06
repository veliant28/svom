import { getJson } from "@/shared/api/http-client";
import { normalizePaginatedListResponse } from "@/shared/api/normalize-list-response";

import type {
  BackofficeAutoDbVehicleFilterOptions,
  BackofficeAutoDbVehicleManufacturer,
  BackofficeAutoDbVehicleModel,
  BackofficeAutoDbVehicleRow,
} from "@/features/backoffice/types/backoffice";

import type { BackofficeListQuery } from "./backoffice-api.types";

export async function getBackofficeAutoDbVehicles(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeAutoDbVehicleRow[] | { results: BackofficeAutoDbVehicleRow[]; count: number }>(
    "/backoffice/autodb/vehicles/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeAutoDbVehicleManufacturers(
  token: string,
  params?: Pick<BackofficeListQuery, "q">,
) {
  return getJson<BackofficeAutoDbVehicleManufacturer[]>("/backoffice/autodb/vehicle-manufacturers/", params, { token });
}

export async function getBackofficeAutoDbVehicleFilterOptions(
  token: string,
  params?: Pick<BackofficeListQuery, "year" | "manufacturer_id" | "model_id" | "modification" | "volume">,
) {
  return getJson<BackofficeAutoDbVehicleFilterOptions>("/backoffice/autodb/vehicle-filter-options/", params, { token });
}

export async function getBackofficeAutoDbVehicleModelsByManufacturer(
  token: string,
  manufacturerId: number,
  params?: Pick<BackofficeListQuery, "q">,
) {
  return getJson<BackofficeAutoDbVehicleModel[]>(
    `/backoffice/autodb/vehicle-manufacturers/${manufacturerId}/models/`,
    params,
    { token },
  );
}
