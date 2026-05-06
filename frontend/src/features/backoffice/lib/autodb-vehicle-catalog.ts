export function isModelSelectorDisabled(manufacturerId: string): boolean {
  return !String(manufacturerId || "").trim();
}

export function isVehicleTableReady(manufacturerId: string, modelId: string): boolean {
  return !isModelSelectorDisabled(manufacturerId) && Boolean(String(modelId || "").trim());
}
