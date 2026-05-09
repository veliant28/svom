export type CompatibilityBadgeState = "fits" | "not_fits" | "has_data" | "none";

export function resolveCompatibilityBadgeState(params: {
  fitsSelectedVehicle?: boolean | null;
  hasFitmentData?: boolean;
  isAutoDbCompatibleDataAvailable?: boolean;
  suppressIncompatibleBadge?: boolean;
}): CompatibilityBadgeState {
  if (params.fitsSelectedVehicle === true) {
    return "fits";
  }
  if (params.fitsSelectedVehicle === false) {
    if (params.suppressIncompatibleBadge) {
      return params.isAutoDbCompatibleDataAvailable || params.hasFitmentData ? "has_data" : "none";
    }
    return "not_fits";
  }
  if (params.isAutoDbCompatibleDataAvailable || params.hasFitmentData) {
    return "has_data";
  }
  return "none";
}
