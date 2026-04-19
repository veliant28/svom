import { useMemo } from "react";

import type { AutocatalogYearOption } from "@/features/garage/types/garage";

export type VehicleCascadeDerivedState = {
  activeYear: number | undefined;
  hasCascadeContext: boolean;
};

export function useVehicleCascadeDerivedState({
  selectedYear,
  years,
  selectedMake,
  selectedModel,
  selectedModification,
  selectedCapacity,
  selectedEngine,
}: {
  selectedYear: string;
  years: AutocatalogYearOption[];
  selectedMake: string;
  selectedModel: string;
  selectedModification: string;
  selectedCapacity: string;
  selectedEngine: string;
}): VehicleCascadeDerivedState {
  const activeYear = useMemo(() => {
    if (!selectedYear) {
      return undefined;
    }

    const parsedYear = Number(selectedYear);
    if (!Number.isInteger(parsedYear)) {
      return undefined;
    }

    return years.some((year) => year.year === parsedYear) ? parsedYear : undefined;
  }, [selectedYear, years]);

  const hasCascadeContext = Boolean(
    selectedMake || selectedModel || selectedModification || selectedCapacity || selectedEngine,
  );

  return {
    activeYear,
    hasCascadeContext,
  };
}
