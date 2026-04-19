import type { GarageVehicle } from "@/features/garage/types/garage";

export function formatGarageVehicleTitle(vehicle: GarageVehicle): string {
  const year = vehicle.year ? String(vehicle.year) : "";
  return [vehicle.brand, vehicle.model, year].filter(Boolean).join(" ");
}

export function formatGarageVehicleSubtitle(vehicle: GarageVehicle): string {
  return [vehicle.modification, vehicle.engine].filter(Boolean).join(" · ");
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
