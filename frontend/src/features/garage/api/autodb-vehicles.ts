import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type {
  AutoDbVehicleCatalogRow,
  AutoDbVehicleFilterOptions,
  AutoDbManufacturerOption,
  AutoDbModelOption,
  AutoDbPassangerCarAttribute,
  AutoDbPassangerCarOption,
} from "@/features/garage/types/garage";

type AutoDbVehicleSearchResponse = {
  manufacturers: AutoDbManufacturerOption[];
  models: AutoDbModelOption[];
  passanger_cars: AutoDbPassangerCarOption[];
};

type AutoDbVehicleCatalogResponse = {
  count: number;
  results: AutoDbVehicleCatalogRow[];
};

export async function getAutoDbManufacturers(): Promise<AutoDbManufacturerOption[]> {
  const data = await getJson<ListResponse<AutoDbManufacturerOption>>("/autodb/vehicles/manufacturers/");
  return normalizeListResponse(data);
}

export async function getAutoDbModels(manufacturerId: number): Promise<AutoDbModelOption[]> {
  const data = await getJson<ListResponse<AutoDbModelOption>>(`/autodb/vehicles/manufacturers/${manufacturerId}/models/`);
  return normalizeListResponse(data);
}

export async function getAutoDbPassangerCars(modelId: number): Promise<AutoDbPassangerCarOption[]> {
  const data = await getJson<ListResponse<AutoDbPassangerCarOption>>(`/autodb/vehicles/models/${modelId}/passanger-cars/`);
  return normalizeListResponse(data);
}

export async function getAutoDbPassangerCar(id: number): Promise<AutoDbPassangerCarOption> {
  return getJson<AutoDbPassangerCarOption>(`/autodb/vehicles/passanger-cars/${id}/`);
}

export async function getAutoDbPassangerCarAttributes(id: number): Promise<AutoDbPassangerCarAttribute[]> {
  const data = await getJson<ListResponse<AutoDbPassangerCarAttribute>>(`/autodb/vehicles/passanger-cars/${id}/attributes/`);
  return normalizeListResponse(data);
}

export async function searchAutoDbVehicles(
  query: string,
  options?: { manufacturerId?: number; modelId?: number },
): Promise<AutoDbVehicleSearchResponse> {
  return getJson<AutoDbVehicleSearchResponse>("/autodb/vehicles/search/", {
    q: query,
    manufacturer_id: options?.manufacturerId,
    model_id: options?.modelId,
  });
}

export async function getAutoDbVehicleFilterOptions(params?: {
  year?: number;
  manufacturer_id?: number;
  model_id?: number;
  modification?: string;
  volume?: string;
  years_only?: boolean;
}): Promise<AutoDbVehicleFilterOptions> {
  return getJson<AutoDbVehicleFilterOptions>("/autodb/vehicles/filter-options/", params);
}

export async function getAutoDbVehicleCatalog(params?: {
  year?: number;
  manufacturer_id?: number;
  model_id?: number;
  modification?: string;
  volume?: string;
  engine?: string;
  page?: number;
  page_size?: number;
}): Promise<AutoDbVehicleCatalogResponse> {
  return getJson<AutoDbVehicleCatalogResponse>("/autodb/vehicles/catalog/", params);
}
