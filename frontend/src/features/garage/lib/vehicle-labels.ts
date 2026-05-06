import type { GarageVehicle } from "@/features/garage/types/garage";
import { normalizeDisplayText } from "@/features/garage/lib/clean-text";

function formatBrandModelTitle(vehicle: GarageVehicle): string {
  const brand = normalizeDisplayText(vehicle.brand);
  const model = normalizeDisplayText(vehicle.model);
  if (!brand) {
    return model;
  }
  const escapedBrand = brand.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const modelWithoutBrandPrefix = model.replace(new RegExp(`^${escapedBrand}[\\s\\-_/,:;]*`, "i"), "").trim();
  if (!modelWithoutBrandPrefix) {
    return brand;
  }
  return `${brand} ${modelWithoutBrandPrefix}`;
}

export function formatGarageVehicleTitle(vehicle: GarageVehicle): string {
  const brandModel = formatBrandModelTitle(vehicle);
  if (brandModel) {
    return brandModel;
  }
  if (vehicle.catalog_source === "autodb_pro") {
    const label = normalizeDisplayText(vehicle.vehicle_label || vehicle.autodb_vehicle_label);
    if (label) {
      return label;
    }
  }
  const year = vehicle.year ? String(vehicle.year) : "";
  return normalizeDisplayText([vehicle.brand, vehicle.model, year].filter(Boolean).join(" "));
}

export function formatGarageVehicleSubtitle(vehicle: GarageVehicle): string {
  return normalizeDisplayText(
    [vehicle.modification, vehicle.engine, vehicle.period || (vehicle.year ? String(vehicle.year) : "")]
      .filter(Boolean)
      .join(" · "),
  );
}

export function formatEngineLabel(engine: {
  engine: string;
  power_hp: number | null;
  power_kw: number | null;
}): string {
  const powerLabel = [
    engine.power_hp ? `${engine.power_hp} hp` : "",
    engine.power_kw ? `${engine.power_kw} kW` : "",
  ]
    .filter(Boolean)
    .join(" / ");

  return [engine.engine, powerLabel].filter(Boolean).join(" · ");
}
