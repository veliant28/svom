import { useEffect } from "react";

import { getAutocatalogCapacities } from "@/features/garage/api/get-autocatalog-capacities";
import { getAutocatalogEngines } from "@/features/garage/api/get-autocatalog-engines";
import { getAutocatalogMakes } from "@/features/garage/api/get-autocatalog-makes";
import { getAutocatalogModels } from "@/features/garage/api/get-autocatalog-models";
import { getAutocatalogModifications } from "@/features/garage/api/get-autocatalog-modifications";
import { getAutocatalogYears } from "@/features/garage/api/get-autocatalog-years";
import type { VehicleCascadeDerivedState } from "@/features/garage/hooks/vehicle-cascade/use-vehicle-cascade-derived-state";
import {
  consumeCascadeStepChange,
  resetAfterCapacityChange,
  resetAfterMakeChange,
  resetAfterModelChange,
  resetAfterModificationChange,
} from "@/features/garage/hooks/vehicle-cascade/use-vehicle-cascade-resets";
import type { VehicleCascadeState } from "@/features/garage/hooks/vehicle-cascade/use-vehicle-cascade-state";

export function useVehicleCascadeOptions(state: VehicleCascadeState, derived: VehicleCascadeDerivedState) {
  const {
    selection: {
      selectedYear,
      selectedMake,
      selectedModel,
      selectedModification,
      selectedCapacity,
      selectedEngine,
    },
    setSelection: {
      setSelectedYear,
      setSelectedMake,
      setSelectedModel,
      setSelectedModification,
      setSelectedCapacity,
      setSelectedEngine,
    },
    options: { years },
    setOptions: { setYears, setMakes, setModels, setModifications, setCapacities, setEngines },
    loading: { isLoadingYears },
    setLoading: {
      setIsLoadingYears,
      setIsLoadingMakes,
      setIsLoadingModels,
      setIsLoadingModifications,
      setIsLoadingCapacities,
      setIsLoadingEngines,
    },
    previous: {
      previousMakeRef,
      previousModelRef,
      previousModificationRef,
      previousCapacityRef,
    },
  } = state;

  const { activeYear, hasCascadeContext } = derived;

  useEffect(() => {
    let isMounted = true;

    async function loadYears() {
      setIsLoadingYears(true);
      try {
        const data = await getAutocatalogYears({
          make: selectedMake ? Number(selectedMake) : undefined,
          model: selectedModel ? Number(selectedModel) : undefined,
          modification: selectedModification || undefined,
          capacity: selectedCapacity || undefined,
          engine: selectedEngine ? Number(selectedEngine) : undefined,
        });
        if (isMounted) {
          setYears(data);
        }
      } catch {
        if (isMounted) {
          setYears([]);
        }
      } finally {
        if (isMounted) {
          setIsLoadingYears(false);
        }
      }
    }

    void loadYears();
    return () => {
      isMounted = false;
    };
  }, [selectedMake, selectedModel, selectedModification, selectedCapacity, selectedEngine, setIsLoadingYears, setYears]);

  useEffect(() => {
    if (isLoadingYears) {
      return;
    }

    if (years.length === 1 && hasCascadeContext) {
      const onlyYear = String(years[0].year);
      if (selectedYear !== onlyYear) {
        setSelectedYear(onlyYear);
      }
      return;
    }

    if (selectedYear && !years.some((year) => String(year.year) === selectedYear)) {
      setSelectedYear("");
    }
  }, [years, isLoadingYears, selectedYear, hasCascadeContext, setSelectedYear]);

  useEffect(() => {
    if (!activeYear) {
      setMakes([]);
      setSelectedMake("");
      resetAfterMakeChange({
        setSelectedModel,
        setSelectedModification,
        setSelectedCapacity,
        setSelectedEngine,
        setModels,
        setModifications,
        setCapacities,
        setEngines,
      });
      setIsLoadingMakes(false);
      return;
    }

    let isMounted = true;

    async function loadMakes() {
      setIsLoadingMakes(true);
      try {
        const data = await getAutocatalogMakes(activeYear);
        if (isMounted) {
          setMakes(data);
          if (selectedMake && !data.some((item) => String(item.id) === selectedMake)) {
            setSelectedMake("");
          }
        }
      } catch {
        if (isMounted) {
          setMakes([]);
        }
      } finally {
        if (isMounted) {
          setIsLoadingMakes(false);
        }
      }
    }

    void loadMakes();
    return () => {
      isMounted = false;
    };
  }, [
    activeYear,
    selectedMake,
    setCapacities,
    setEngines,
    setIsLoadingMakes,
    setMakes,
    setModels,
    setModifications,
    setSelectedCapacity,
    setSelectedEngine,
    setSelectedMake,
    setSelectedModel,
    setSelectedModification,
  ]);

  useEffect(() => {
    const makeChanged = consumeCascadeStepChange(previousMakeRef, selectedMake);

    if (makeChanged) {
      resetAfterMakeChange({
        setSelectedModel,
        setSelectedModification,
        setSelectedCapacity,
        setSelectedEngine,
        setModels,
        setModifications,
        setCapacities,
        setEngines,
      });
    }

    if (!selectedMake) {
      setIsLoadingModels(false);
      return;
    }

    let isMounted = true;

    async function loadModels() {
      setIsLoadingModels(true);
      try {
        const makeId = Number(selectedMake);
        const data = await getAutocatalogModels(makeId, activeYear);
        if (isMounted) {
          setModels(data);
          if (selectedModel && !data.some((item) => String(item.id) === selectedModel)) {
            setSelectedModel("");
          }
        }
      } catch {
        if (isMounted) {
          setModels([]);
        }
      } finally {
        if (isMounted) {
          setIsLoadingModels(false);
        }
      }
    }

    void loadModels();
    return () => {
      isMounted = false;
    };
  }, [selectedMake, activeYear, selectedModel, previousMakeRef, setSelectedModel, setSelectedModification, setSelectedCapacity, setSelectedEngine, setModels, setModifications, setCapacities, setEngines, setIsLoadingModels]);

  useEffect(() => {
    const modelChanged = consumeCascadeStepChange(previousModelRef, selectedModel);

    if (modelChanged) {
      resetAfterModelChange({
        setSelectedModification,
        setSelectedCapacity,
        setSelectedEngine,
        setModifications,
        setCapacities,
        setEngines,
      });
    }

    if (!selectedModel) {
      setIsLoadingModifications(false);
      return;
    }

    let isMounted = true;

    async function loadModifications() {
      setIsLoadingModifications(true);
      try {
        const makeId = Number(selectedMake);
        const modelId = Number(selectedModel);
        const data = await getAutocatalogModifications(makeId, modelId, activeYear);
        if (isMounted) {
          setModifications(data);
          if (selectedModification && !data.some((item) => item.modification === selectedModification)) {
            setSelectedModification("");
          }
        }
      } catch {
        if (isMounted) {
          setModifications([]);
        }
      } finally {
        if (isMounted) {
          setIsLoadingModifications(false);
        }
      }
    }

    void loadModifications();
    return () => {
      isMounted = false;
    };
  }, [selectedMake, selectedModel, activeYear, selectedModification, previousModelRef, setSelectedModification, setSelectedCapacity, setSelectedEngine, setModifications, setCapacities, setEngines, setIsLoadingModifications]);

  useEffect(() => {
    const modificationChanged = consumeCascadeStepChange(previousModificationRef, selectedModification);

    if (modificationChanged) {
      resetAfterModificationChange({
        setSelectedCapacity,
        setSelectedEngine,
        setCapacities,
        setEngines,
      });
    }

    if (!selectedModification) {
      setIsLoadingCapacities(false);
      return;
    }

    let isMounted = true;

    async function loadCapacities() {
      setIsLoadingCapacities(true);
      try {
        const makeId = Number(selectedMake);
        const modelId = Number(selectedModel);
        const data = await getAutocatalogCapacities(makeId, modelId, selectedModification, activeYear);
        if (isMounted) {
          setCapacities(data);
          if (selectedCapacity && !data.some((item) => item.capacity === selectedCapacity)) {
            setSelectedCapacity("");
          }
        }
      } catch {
        if (isMounted) {
          setCapacities([]);
        }
      } finally {
        if (isMounted) {
          setIsLoadingCapacities(false);
        }
      }
    }

    void loadCapacities();
    return () => {
      isMounted = false;
    };
  }, [selectedMake, selectedModel, selectedModification, activeYear, selectedCapacity, previousModificationRef, setSelectedCapacity, setSelectedEngine, setCapacities, setEngines, setIsLoadingCapacities]);

  useEffect(() => {
    const capacityChanged = consumeCascadeStepChange(previousCapacityRef, selectedCapacity);

    if (capacityChanged) {
      resetAfterCapacityChange({
        setSelectedEngine,
        setEngines,
      });
    }

    if (!selectedCapacity) {
      setIsLoadingEngines(false);
      return;
    }

    let isMounted = true;

    async function loadEngines() {
      setIsLoadingEngines(true);
      try {
        const makeId = Number(selectedMake);
        const modelId = Number(selectedModel);
        const data = await getAutocatalogEngines(makeId, modelId, selectedModification, selectedCapacity, activeYear);
        if (isMounted) {
          setEngines(data);
          if (selectedEngine && !data.some((item) => String(item.id) === selectedEngine)) {
            setSelectedEngine("");
          }
        }
      } catch {
        if (isMounted) {
          setEngines([]);
        }
      } finally {
        if (isMounted) {
          setIsLoadingEngines(false);
        }
      }
    }

    void loadEngines();
    return () => {
      isMounted = false;
    };
  }, [selectedMake, selectedModel, selectedModification, selectedCapacity, activeYear, selectedEngine, previousCapacityRef, setSelectedEngine, setEngines, setIsLoadingEngines]);
}
