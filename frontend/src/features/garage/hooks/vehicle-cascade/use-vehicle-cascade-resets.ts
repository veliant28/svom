import type { Dispatch, MutableRefObject, SetStateAction } from "react";

type StringSetter = Dispatch<SetStateAction<string>>;
type ArraySetter<T> = Dispatch<SetStateAction<T[]>>;

export function consumeCascadeStepChange(ref: MutableRefObject<string>, currentValue: string): boolean {
  const changed = ref.current !== currentValue;
  ref.current = currentValue;
  return changed;
}

export function resetAfterMakeChange<TModel, TModification, TCapacity, TEngine>({
  setSelectedModel,
  setSelectedModification,
  setSelectedCapacity,
  setSelectedEngine,
  setModels,
  setModifications,
  setCapacities,
  setEngines,
}: {
  setSelectedModel: StringSetter;
  setSelectedModification: StringSetter;
  setSelectedCapacity: StringSetter;
  setSelectedEngine: StringSetter;
  setModels: ArraySetter<TModel>;
  setModifications: ArraySetter<TModification>;
  setCapacities: ArraySetter<TCapacity>;
  setEngines: ArraySetter<TEngine>;
}) {
  setSelectedModel("");
  setSelectedModification("");
  setSelectedCapacity("");
  setSelectedEngine("");
  setModels([]);
  setModifications([]);
  setCapacities([]);
  setEngines([]);
}

export function resetAfterModelChange<TModification, TCapacity, TEngine>({
  setSelectedModification,
  setSelectedCapacity,
  setSelectedEngine,
  setModifications,
  setCapacities,
  setEngines,
}: {
  setSelectedModification: StringSetter;
  setSelectedCapacity: StringSetter;
  setSelectedEngine: StringSetter;
  setModifications: ArraySetter<TModification>;
  setCapacities: ArraySetter<TCapacity>;
  setEngines: ArraySetter<TEngine>;
}) {
  setSelectedModification("");
  setSelectedCapacity("");
  setSelectedEngine("");
  setModifications([]);
  setCapacities([]);
  setEngines([]);
}

export function resetAfterModificationChange<TCapacity, TEngine>({
  setSelectedCapacity,
  setSelectedEngine,
  setCapacities,
  setEngines,
}: {
  setSelectedCapacity: StringSetter;
  setSelectedEngine: StringSetter;
  setCapacities: ArraySetter<TCapacity>;
  setEngines: ArraySetter<TEngine>;
}) {
  setSelectedCapacity("");
  setSelectedEngine("");
  setCapacities([]);
  setEngines([]);
}

export function resetAfterCapacityChange<TEngine>({
  setSelectedEngine,
  setEngines,
}: {
  setSelectedEngine: StringSetter;
  setEngines: ArraySetter<TEngine>;
}) {
  setSelectedEngine("");
  setEngines([]);
}
