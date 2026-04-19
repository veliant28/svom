export type BackofficeVehicleMake = {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeVehicleModel = {
  id: string;
  make: string;
  make_name: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeVehicleGeneration = {
  id: string;
  model: string;
  model_name: string;
  make_name: string;
  name: string;
  year_start: number | null;
  year_end: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeVehicleEngine = {
  id: string;
  generation: string;
  generation_name: string;
  model_name: string;
  make_name: string;
  name: string;
  code: string;
  fuel_type: string;
  displacement_cc: number | null;
  power_hp: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeVehicleModification = {
  id: string;
  engine: string;
  engine_name: string;
  generation_name: string;
  model_name: string;
  make_name: string;
  name: string;
  body_type: string;
  transmission: string;
  drivetrain: string;
  year_start: number | null;
  year_end: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeProductFitment = {
  id: string;
  product: string;
  product_name: string;
  product_sku: string;
  modification: string;
  modification_name: string;
  engine_name: string;
  generation_name: string;
  model_name: string;
  make_name: string;
  note: string;
  is_exact: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeAutocatalogCar = {
  year: number | null;
  make: string;
  model: string;
  modification: string;
  capacity: string;
  engine: string;
  hp: number | null;
  kw: number | null;
};

export type BackofficeAutocatalogFilterOptions = {
  years: number[];
  makes: string[];
  models: string[];
  modifications: string[];
  capacities: string[];
  engines: string[];
};
