import { useMemo } from "react";

import type { VehicleCascadeSelectionSetters } from "@/features/garage/hooks/vehicle-cascade/use-vehicle-cascade-state";

export function useVehicleCascadeApply(setSelection: VehicleCascadeSelectionSetters) {
  const {
    setSelectedYear,
    setSelectedMake,
    setSelectedModel,
    setSelectedModification,
    setSelectedCapacity,
    setSelectedEngine,
  } = setSelection;

  return useMemo(
    () => ({
      setSelectedYear,
      setSelectedMake,
      setSelectedModel,
      setSelectedModification,
      setSelectedCapacity,
      setSelectedEngine,
    }),
    [setSelectedYear, setSelectedMake, setSelectedModel, setSelectedModification, setSelectedCapacity, setSelectedEngine],
  );
}
