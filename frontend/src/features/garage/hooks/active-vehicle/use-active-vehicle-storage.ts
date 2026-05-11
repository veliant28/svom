import { useEffect, useRef, useState } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import type { ActiveVehicleSource } from "@/features/garage/hooks/active-vehicle/active-vehicle-context";

const ACTIVE_VEHICLE_STORAGE_KEY = "svom.storefront.activeVehicle.v1";

type PersistedActiveVehicle = {
  source: ActiveVehicleSource;
  value: string | null;
  manual: boolean;
};

type StringSetter = Dispatch<SetStateAction<string | null>>;
type NumberSetter = Dispatch<SetStateAction<number | null>>;
type SourceSetter = Dispatch<SetStateAction<ActiveVehicleSource>>;
type BoolSetter = Dispatch<SetStateAction<boolean>>;

function readPersistedActiveVehicle(): PersistedActiveVehicle {
  if (typeof window === "undefined") {
    return { source: "none", value: null, manual: false };
  }

  try {
    const raw = window.localStorage.getItem(ACTIVE_VEHICLE_STORAGE_KEY);
    if (!raw) {
      return { source: "none", value: null, manual: false };
    }
    const parsed = JSON.parse(raw) as Partial<PersistedActiveVehicle>;
    const source: ActiveVehicleSource =
      parsed.source === "garage" ||
      parsed.source === "temporary_autodb" ||
      parsed.source === "none"
        ? parsed.source
        : "none";
    const value = typeof parsed.value === "string" && parsed.value.trim().length > 0 ? parsed.value : null;
    return {
      source,
      value,
      manual: parsed.manual === true,
    };
  } catch {
    return { source: "none", value: null, manual: false };
  }
}

function writePersistedActiveVehicle(payload: PersistedActiveVehicle) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(ACTIVE_VEHICLE_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore persistence failures in private/incognito modes.
  }
}

export function useActiveVehicleStorage({
  activeVehicleSource,
  activeGarageVehicleId,
  activeTemporaryAutoDbPassangerCarId,
  isManualSelection,
  setActiveVehicleSource,
  setActiveGarageVehicleId,
  setActiveTemporaryAutoDbPassangerCarId,
  setIsManualSelection,
}: {
  activeVehicleSource: ActiveVehicleSource;
  activeGarageVehicleId: string | null;
  activeTemporaryAutoDbPassangerCarId: number | null;
  isManualSelection: boolean;
  setActiveVehicleSource: SourceSetter;
  setActiveGarageVehicleId: StringSetter;
  setActiveTemporaryAutoDbPassangerCarId: NumberSetter;
  setIsManualSelection: BoolSetter;
}): { hasHydratedFromStorage: MutableRefObject<boolean> } {
  const hasHydratedFromStorage = useRef(false);
  const [hasCompletedStorageHydration, setHasCompletedStorageHydration] = useState(false);

  useEffect(() => {
    const persisted = readPersistedActiveVehicle();
    setActiveVehicleSource(persisted.source);
    setIsManualSelection(persisted.manual);

    if (persisted.source === "garage") {
      setActiveGarageVehicleId(persisted.value);
      setActiveTemporaryAutoDbPassangerCarId(null);
    } else if (persisted.source === "temporary_autodb") {
      const parsed = persisted.value ? Number(persisted.value) : NaN;
      if (Number.isInteger(parsed) && parsed > 0) {
        setActiveTemporaryAutoDbPassangerCarId(parsed);
      } else {
        setActiveVehicleSource("none");
      }
      setActiveGarageVehicleId(null);
    } else {
      setActiveGarageVehicleId(null);
      setActiveTemporaryAutoDbPassangerCarId(null);
    }

    hasHydratedFromStorage.current = true;
    setHasCompletedStorageHydration(true);
  }, [
    setActiveGarageVehicleId,
    setActiveTemporaryAutoDbPassangerCarId,
    setActiveVehicleSource,
    setIsManualSelection,
  ]);

  useEffect(() => {
    if (!hasCompletedStorageHydration) {
      return;
    }

    const value =
      activeVehicleSource === "garage"
        ? activeGarageVehicleId
        : activeVehicleSource === "temporary_autodb" && activeTemporaryAutoDbPassangerCarId
          ? String(activeTemporaryAutoDbPassangerCarId)
          : null;

    writePersistedActiveVehicle({
      source: activeVehicleSource,
      value,
      manual: isManualSelection,
    });
  }, [
    activeGarageVehicleId,
    activeTemporaryAutoDbPassangerCarId,
    activeVehicleSource,
    hasCompletedStorageHydration,
    isManualSelection,
  ]);

  return { hasHydratedFromStorage };
}
