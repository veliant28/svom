import { useRef, useState } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import type {
  AutocatalogCapacityOption,
  AutocatalogEngineOption,
  AutocatalogMakeOption,
  AutocatalogModelOption,
  AutocatalogModificationOption,
  AutocatalogYearOption,
} from "@/features/garage/types/garage";

type StringSetter = Dispatch<SetStateAction<string>>;
type BoolSetter = Dispatch<SetStateAction<boolean>>;

type ArraySetter<T> = Dispatch<SetStateAction<T[]>>;

export type VehicleCascadeSelectionState = {
  selectedYear: string;
  selectedMake: string;
  selectedModel: string;
  selectedModification: string;
  selectedCapacity: string;
  selectedEngine: string;
};

export type VehicleCascadeSelectionSetters = {
  setSelectedYear: StringSetter;
  setSelectedMake: StringSetter;
  setSelectedModel: StringSetter;
  setSelectedModification: StringSetter;
  setSelectedCapacity: StringSetter;
  setSelectedEngine: StringSetter;
};

export type VehicleCascadeOptionsState = {
  years: AutocatalogYearOption[];
  makes: AutocatalogMakeOption[];
  models: AutocatalogModelOption[];
  modifications: AutocatalogModificationOption[];
  capacities: AutocatalogCapacityOption[];
  engines: AutocatalogEngineOption[];
};

export type VehicleCascadeOptionsSetters = {
  setYears: ArraySetter<AutocatalogYearOption>;
  setMakes: ArraySetter<AutocatalogMakeOption>;
  setModels: ArraySetter<AutocatalogModelOption>;
  setModifications: ArraySetter<AutocatalogModificationOption>;
  setCapacities: ArraySetter<AutocatalogCapacityOption>;
  setEngines: ArraySetter<AutocatalogEngineOption>;
};

export type VehicleCascadeLoadingState = {
  isLoadingYears: boolean;
  isLoadingMakes: boolean;
  isLoadingModels: boolean;
  isLoadingModifications: boolean;
  isLoadingCapacities: boolean;
  isLoadingEngines: boolean;
};

export type VehicleCascadeLoadingSetters = {
  setIsLoadingYears: BoolSetter;
  setIsLoadingMakes: BoolSetter;
  setIsLoadingModels: BoolSetter;
  setIsLoadingModifications: BoolSetter;
  setIsLoadingCapacities: BoolSetter;
  setIsLoadingEngines: BoolSetter;
};

export type VehicleCascadePreviousRefs = {
  previousMakeRef: MutableRefObject<string>;
  previousModelRef: MutableRefObject<string>;
  previousModificationRef: MutableRefObject<string>;
  previousCapacityRef: MutableRefObject<string>;
};

export type VehicleCascadeState = {
  selection: VehicleCascadeSelectionState;
  setSelection: VehicleCascadeSelectionSetters;
  options: VehicleCascadeOptionsState;
  setOptions: VehicleCascadeOptionsSetters;
  loading: VehicleCascadeLoadingState;
  setLoading: VehicleCascadeLoadingSetters;
  previous: VehicleCascadePreviousRefs;
};

export function useVehicleCascadeState(): VehicleCascadeState {
  const [selectedYear, setSelectedYear] = useState<string>("");
  const [selectedMake, setSelectedMake] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedModification, setSelectedModification] = useState<string>("");
  const [selectedCapacity, setSelectedCapacity] = useState<string>("");
  const [selectedEngine, setSelectedEngine] = useState<string>("");

  const [years, setYears] = useState<AutocatalogYearOption[]>([]);
  const [makes, setMakes] = useState<AutocatalogMakeOption[]>([]);
  const [models, setModels] = useState<AutocatalogModelOption[]>([]);
  const [modifications, setModifications] = useState<AutocatalogModificationOption[]>([]);
  const [capacities, setCapacities] = useState<AutocatalogCapacityOption[]>([]);
  const [engines, setEngines] = useState<AutocatalogEngineOption[]>([]);

  const [isLoadingYears, setIsLoadingYears] = useState(false);
  const [isLoadingMakes, setIsLoadingMakes] = useState(false);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [isLoadingModifications, setIsLoadingModifications] = useState(false);
  const [isLoadingCapacities, setIsLoadingCapacities] = useState(false);
  const [isLoadingEngines, setIsLoadingEngines] = useState(false);

  const previousMakeRef = useRef<string>("");
  const previousModelRef = useRef<string>("");
  const previousModificationRef = useRef<string>("");
  const previousCapacityRef = useRef<string>("");

  return {
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
    options: {
      years,
      makes,
      models,
      modifications,
      capacities,
      engines,
    },
    setOptions: {
      setYears,
      setMakes,
      setModels,
      setModifications,
      setCapacities,
      setEngines,
    },
    loading: {
      isLoadingYears,
      isLoadingMakes,
      isLoadingModels,
      isLoadingModifications,
      isLoadingCapacities,
      isLoadingEngines,
    },
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
  };
}
