"use client";

import { useVehicleCascadeApply } from "@/features/garage/hooks/vehicle-cascade/use-vehicle-cascade-apply";
import { useVehicleCascadeDerivedState } from "@/features/garage/hooks/vehicle-cascade/use-vehicle-cascade-derived-state";
import { useVehicleCascadeOptions } from "@/features/garage/hooks/vehicle-cascade/use-vehicle-cascade-options";
import { useVehicleCascadeState } from "@/features/garage/hooks/vehicle-cascade/use-vehicle-cascade-state";

export function useVehicleCascade() {
  const state = useVehicleCascadeState();

  const derived = useVehicleCascadeDerivedState({
    selectedYear: state.selection.selectedYear,
    years: state.options.years,
    selectedMake: state.selection.selectedMake,
    selectedModel: state.selection.selectedModel,
    selectedModification: state.selection.selectedModification,
    selectedCapacity: state.selection.selectedCapacity,
    selectedEngine: state.selection.selectedEngine,
  });

  useVehicleCascadeOptions(state, derived);

  const apply = useVehicleCascadeApply(state.setSelection);

  return {
    selectedYear: state.selection.selectedYear,
    selectedMake: state.selection.selectedMake,
    selectedModel: state.selection.selectedModel,
    selectedModification: state.selection.selectedModification,
    selectedCapacity: state.selection.selectedCapacity,
    selectedEngine: state.selection.selectedEngine,
    setSelectedYear: apply.setSelectedYear,
    setSelectedMake: apply.setSelectedMake,
    setSelectedModel: apply.setSelectedModel,
    setSelectedModification: apply.setSelectedModification,
    setSelectedCapacity: apply.setSelectedCapacity,
    setSelectedEngine: apply.setSelectedEngine,
    years: state.options.years,
    makes: state.options.makes,
    models: state.options.models,
    modifications: state.options.modifications,
    capacities: state.options.capacities,
    engines: state.options.engines,
    isLoadingYears: state.loading.isLoadingYears,
    isLoadingMakes: state.loading.isLoadingMakes,
    isLoadingModels: state.loading.isLoadingModels,
    isLoadingModifications: state.loading.isLoadingModifications,
    isLoadingCapacities: state.loading.isLoadingCapacities,
    isLoadingEngines: state.loading.isLoadingEngines,
  };
}
