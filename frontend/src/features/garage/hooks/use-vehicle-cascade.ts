"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { getAutocatalogCapacities } from "@/features/garage/api/get-autocatalog-capacities";
import { getAutocatalogEngines } from "@/features/garage/api/get-autocatalog-engines";
import { getAutocatalogMakes } from "@/features/garage/api/get-autocatalog-makes";
import { getAutocatalogModels } from "@/features/garage/api/get-autocatalog-models";
import { getAutocatalogModifications } from "@/features/garage/api/get-autocatalog-modifications";
import { getAutocatalogYears } from "@/features/garage/api/get-autocatalog-years";
import type {
  AutocatalogCapacityOption,
  AutocatalogEngineOption,
  AutocatalogMakeOption,
  AutocatalogModelOption,
  AutocatalogModificationOption,
  AutocatalogYearOption,
} from "@/features/garage/types/garage";

export function useVehicleCascade() {
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
  }, [selectedMake, selectedModel, selectedModification, selectedCapacity, selectedEngine]);

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
  }, [years, isLoadingYears, selectedYear, hasCascadeContext]);

  useEffect(() => {
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
  }, [activeYear, selectedMake]);

  useEffect(() => {
    const makeChanged = previousMakeRef.current !== selectedMake;
    previousMakeRef.current = selectedMake;

    if (makeChanged) {
      setSelectedModel("");
      setSelectedModification("");
      setSelectedCapacity("");
      setSelectedEngine("");
      setModels([]);
      setModifications([]);
      setCapacities([]);
      setEngines([]);
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
  }, [selectedMake, activeYear, selectedModel]);

  useEffect(() => {
    const modelChanged = previousModelRef.current !== selectedModel;
    previousModelRef.current = selectedModel;

    if (modelChanged) {
      setSelectedModification("");
      setSelectedCapacity("");
      setSelectedEngine("");
      setModifications([]);
      setCapacities([]);
      setEngines([]);
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
  }, [selectedMake, selectedModel, activeYear, selectedModification]);

  useEffect(() => {
    const modificationChanged = previousModificationRef.current !== selectedModification;
    previousModificationRef.current = selectedModification;

    if (modificationChanged) {
      setSelectedCapacity("");
      setSelectedEngine("");
      setCapacities([]);
      setEngines([]);
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
  }, [selectedMake, selectedModel, selectedModification, activeYear, selectedCapacity]);

  useEffect(() => {
    const capacityChanged = previousCapacityRef.current !== selectedCapacity;
    previousCapacityRef.current = selectedCapacity;

    if (capacityChanged) {
      setSelectedEngine("");
      setEngines([]);
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
  }, [selectedMake, selectedModel, selectedModification, selectedCapacity, activeYear, selectedEngine]);

  return {
    selectedYear,
    selectedMake,
    selectedModel,
    selectedModification,
    selectedCapacity,
    selectedEngine,
    setSelectedYear,
    setSelectedMake,
    setSelectedModel,
    setSelectedModification,
    setSelectedCapacity,
    setSelectedEngine,
    years,
    makes,
    models,
    modifications,
    capacities,
    engines,
    isLoadingYears,
    isLoadingMakes,
    isLoadingModels,
    isLoadingModifications,
    isLoadingCapacities,
    isLoadingEngines,
  };
}
