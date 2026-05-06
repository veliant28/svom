const TRUE_VALUES = new Set(["1", "true", "yes", "on"]);

export function isTruthyFlag(value: string | undefined | null): boolean {
  return TRUE_VALUES.has(String(value ?? "").trim().toLowerCase());
}

// Garage/header vehicle selector is pinned to local Auto_DB_Pro source.
export const isAutoDbVehicleCatalogEnabled = true;
