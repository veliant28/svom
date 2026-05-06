export type GarageVehicle = {
  id: string;
  user: string;
  catalog_source: "legacy" | "autodb_pro";
  car_modification_id: number | null;
  autodb_manufacturer_id: number | null;
  autodb_model_id: number | null;
  autodb_passanger_car_id: number | null;
  autodb_vehicle_label: string;
  vehicle_label: string;
  brand: string;
  model: string;
  year: number | null;
  period: string;
  modification: string;
  engine: string;
  power_hp: number | null;
  power_kw: number | null;
  is_primary: boolean;
};

export type AutocatalogMakeOption = {
  id: number;
  name: string;
  slug: string;
};

export type AutocatalogModelOption = {
  id: number;
  name: string;
  slug: string;
  make: number;
  make_name: string;
};

export type AutocatalogYearOption = {
  year: number;
};

export type AutocatalogModificationOption = {
  modification: string;
};

export type AutocatalogCapacityOption = {
  capacity: string;
};

export type AutocatalogEngineOption = {
  id: number;
  brand: string;
  model: string;
  year: number | null;
  modification: string;
  engine: string;
  capacity: string;
  power_hp: number | null;
  power_kw: number | null;
};

export type GarageVehicleCreatePayload = {
  car_modification?: number;
  year?: number;
  autodb_manufacturer_id?: number;
  autodb_model_id?: number;
  autodb_passanger_car_id?: number;
  autodb_vehicle_label?: string;
  autodb_modification?: string;
  autodb_engine?: string;
  autodb_power_hp?: number | null;
  autodb_power_kw?: number | null;
  is_primary?: boolean;
};

export type GarageVehicleUpdatePayload = {
  is_primary?: boolean;
};

export type AutoDbManufacturerOption = {
  id: number;
  name: string;
  description: string;
  full_description: string;
};

export type AutoDbModelOption = {
  id: number;
  manufacturer_id: number;
  name: string;
  description: string;
  full_description: string;
  construction_interval?: string;
};

export type AutoDbPassangerCarOption = {
  id: number;
  model_id: number;
  name: string;
  description: string;
  full_description: string;
  construction_interval: string;
  year_from: number | null;
  year_to: number | null;
  raw_construction_interval: string;
};

export type AutoDbPassangerCarAttribute = {
  title: string;
  value: string;
  type: string;
  unit: string;
};

export type AutoDbVehicleFilterOptions = {
  years: number[];
  manufacturers: Array<{ id: number; name: string }>;
  models: Array<{ id: number; name: string }>;
  modifications: string[];
  volumes: string[];
  engines: string[];
};

export type AutoDbVehicleCatalogRow = {
  passanger_car_id: number;
  manufacturer_id: number | null;
  model_id: number | null;
  make: string;
  model: string;
  modification: string;
  period: string;
  period_raw: string;
  volume: string;
  engine: string;
  hp: string;
  kw: string;
};
