export type GarageVehicle = {
  id: string;
  user: string;
  catalog_source: "autodb_pro";
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

export type GarageVehicleCreatePayload = {
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
