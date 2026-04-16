export type GarageVehicle = {
  id: string;
  user: string;
  car_modification_id: number;
  brand: string;
  model: string;
  year: number | null;
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
  car_modification: number;
  is_primary?: boolean;
};

export type GarageVehicleUpdatePayload = {
  is_primary?: boolean;
};
