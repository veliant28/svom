import { useCallback, useEffect, useRef, type Dispatch, type SetStateAction } from "react";

import {
  lookupBackofficeNovaPoshtaSettlements,
  lookupBackofficeNovaPoshtaStreets,
  lookupBackofficeNovaPoshtaWarehouses,
} from "@/features/backoffice/api/orders-api";
import { formatWarehouseLookupDisplay } from "@/features/backoffice/components/orders/nova-poshta-senders.helpers";
import type {
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
  BackofficeNovaPoshtaLookupWarehouse,
} from "@/features/backoffice/types/nova-poshta.types";

type LocaleCode = "uk" | "ru" | "en";

export function useNovaPoshtaSendersLookupPanel({
  token,
  activeLookupSenderId,
  lookupSettlementRef,
  lookupCityRef,
  lookupLocale,
  settlementQuery,
  streetQuery,
  warehouseQuery,
  setLookupSettlementRef,
  setLookupCityRef,
  setSettlementQuery,
  setStreetQuery,
  setWarehouseQuery,
  setSettlements,
  setStreets,
  setWarehouses,
  setSettlementLoading,
  setStreetLoading,
  setWarehouseLoading,
  setActiveSettlementIndex,
  setActiveStreetIndex,
  setActiveWarehouseIndex,
}: {
  token: string | null;
  activeLookupSenderId: string;
  lookupSettlementRef: string;
  lookupCityRef: string;
  lookupLocale: LocaleCode;
  settlementQuery: string;
  streetQuery: string;
  warehouseQuery: string;
  setLookupSettlementRef: Dispatch<SetStateAction<string>>;
  setLookupCityRef: Dispatch<SetStateAction<string>>;
  setSettlementQuery: Dispatch<SetStateAction<string>>;
  setStreetQuery: Dispatch<SetStateAction<string>>;
  setWarehouseQuery: Dispatch<SetStateAction<string>>;
  setSettlements: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setStreets: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupStreet[]>>;
  setWarehouses: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupWarehouse[]>>;
  setSettlementLoading: Dispatch<SetStateAction<boolean>>;
  setStreetLoading: Dispatch<SetStateAction<boolean>>;
  setWarehouseLoading: Dispatch<SetStateAction<boolean>>;
  setActiveSettlementIndex: Dispatch<SetStateAction<number>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
}) {
  const settlementRequestRef = useRef(0);
  const streetRequestRef = useRef(0);
  const warehouseRequestRef = useRef(0);
  const skipNextSettlementLookupRef = useRef(false);
  const skipNextStreetLookupRef = useRef(false);
  const skipNextWarehouseLookupRef = useRef(false);

  const runSettlementLookup = useCallback(async (rawQuery: string) => {
    const query = rawQuery.trim();
    if (!token || !activeLookupSenderId || query.length < 2) {
      settlementRequestRef.current += 1;
      setSettlements([]);
      setActiveSettlementIndex(-1);
      setSettlementLoading(false);
      return;
    }

    const requestId = settlementRequestRef.current + 1;
    settlementRequestRef.current = requestId;
    setSettlementLoading(true);
    try {
      const response = await lookupBackofficeNovaPoshtaSettlements(token, {
        sender_profile_id: activeLookupSenderId,
        query,
        locale: lookupLocale,
      });
      if (settlementRequestRef.current !== requestId) {
        return;
      }
      setSettlements(response.results);
      setActiveSettlementIndex(response.results.length > 0 ? 0 : -1);
    } catch {
      if (settlementRequestRef.current !== requestId) {
        return;
      }
      setSettlements([]);
      setActiveSettlementIndex(-1);
    } finally {
      if (settlementRequestRef.current === requestId) {
        setSettlementLoading(false);
      }
    }
  }, [activeLookupSenderId, lookupLocale, setActiveSettlementIndex, setSettlementLoading, setSettlements, token]);

  const applySettlementLookup = useCallback((item: BackofficeNovaPoshtaLookupSettlement) => {
    skipNextSettlementLookupRef.current = true;
    setLookupSettlementRef(item.settlement_ref || item.ref || "");
    setLookupCityRef(item.delivery_city_ref || item.ref || "");
    setSettlementQuery(item.label || item.main_description || "");
    setStreets([]);
    setWarehouses([]);
    setStreetQuery("");
    setWarehouseQuery("");
    setActiveSettlementIndex(-1);
    setActiveStreetIndex(-1);
    setActiveWarehouseIndex(-1);
  }, [
    setActiveSettlementIndex,
    setActiveStreetIndex,
    setActiveWarehouseIndex,
    setLookupCityRef,
    setLookupSettlementRef,
    setSettlementQuery,
    setStreetQuery,
    setStreets,
    setWarehouseQuery,
    setWarehouses,
  ]);

  const runStreetLookup = useCallback(async (rawQuery: string, lookupSettlementRef: string) => {
    const query = rawQuery.trim();
    if (!token || !activeLookupSenderId || !lookupSettlementRef || query.length < 2) {
      streetRequestRef.current += 1;
      setStreets([]);
      setActiveStreetIndex(-1);
      setStreetLoading(false);
      return;
    }

    const requestId = streetRequestRef.current + 1;
    streetRequestRef.current = requestId;
    setStreetLoading(true);
    try {
      const response = await lookupBackofficeNovaPoshtaStreets(token, {
        sender_profile_id: activeLookupSenderId,
        settlement_ref: lookupSettlementRef,
        query,
        locale: lookupLocale,
      });
      if (streetRequestRef.current !== requestId) {
        return;
      }
      setStreets(response.results);
      setActiveStreetIndex(response.results.length > 0 ? 0 : -1);
    } catch {
      if (streetRequestRef.current !== requestId) {
        return;
      }
      setStreets([]);
      setActiveStreetIndex(-1);
    } finally {
      if (streetRequestRef.current === requestId) {
        setStreetLoading(false);
      }
    }
  }, [activeLookupSenderId, lookupLocale, setActiveStreetIndex, setStreetLoading, setStreets, token]);

  const applyStreetLookup = useCallback((item: BackofficeNovaPoshtaLookupStreet) => {
    skipNextStreetLookupRef.current = true;
    setStreetQuery(item.label || item.street_name || "");
    setStreets([]);
    setActiveStreetIndex(-1);
  }, [setActiveStreetIndex, setStreetQuery, setStreets]);

  const runWarehouseLookup = useCallback(async (rawQuery: string) => {
    const query = rawQuery.trim();
    const isDigitsOnly = /^\d+$/.test(query);
    const minLength = isDigitsOnly ? 1 : 2;
    if (!token || !activeLookupSenderId || !lookupCityRef || query.length < minLength) {
      warehouseRequestRef.current += 1;
      setWarehouses([]);
      setActiveWarehouseIndex(-1);
      setWarehouseLoading(false);
      return;
    }

    const requestId = warehouseRequestRef.current + 1;
    warehouseRequestRef.current = requestId;
    setWarehouseLoading(true);
    try {
      const response = await lookupBackofficeNovaPoshtaWarehouses(token, {
        sender_profile_id: activeLookupSenderId,
        city_ref: lookupCityRef,
        query,
        locale: lookupLocale,
      });
      if (warehouseRequestRef.current !== requestId) {
        return;
      }
      setWarehouses(response.results);
      setActiveWarehouseIndex(response.results.length > 0 ? 0 : -1);
    } catch {
      if (warehouseRequestRef.current !== requestId) {
        return;
      }
      setWarehouses([]);
      setActiveWarehouseIndex(-1);
    } finally {
      if (warehouseRequestRef.current === requestId) {
        setWarehouseLoading(false);
      }
    }
  }, [activeLookupSenderId, lookupCityRef, lookupLocale, setActiveWarehouseIndex, setWarehouseLoading, setWarehouses, token]);

  const applyWarehouseLookup = useCallback((item: BackofficeNovaPoshtaLookupWarehouse) => {
    const formatted = formatWarehouseLookupDisplay(item);
    skipNextWarehouseLookupRef.current = true;
    setWarehouseQuery(formatted.label);
    setWarehouses([]);
    setActiveWarehouseIndex(-1);
  }, [setActiveWarehouseIndex, setWarehouseQuery, setWarehouses]);

  useEffect(() => {
    if (skipNextSettlementLookupRef.current) {
      skipNextSettlementLookupRef.current = false;
      return;
    }
    const timerId = window.setTimeout(() => {
      void runSettlementLookup(settlementQuery);
    }, 280);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [runSettlementLookup, settlementQuery]);

  useEffect(() => {
    if (skipNextStreetLookupRef.current) {
      skipNextStreetLookupRef.current = false;
      return;
    }
    const timerId = window.setTimeout(() => {
      void runStreetLookup(streetQuery, lookupSettlementRef);
    }, 280);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [lookupSettlementRef, runStreetLookup, streetQuery]);

  useEffect(() => {
    if (skipNextWarehouseLookupRef.current) {
      skipNextWarehouseLookupRef.current = false;
      return;
    }
    const timerId = window.setTimeout(() => {
      void runWarehouseLookup(warehouseQuery);
    }, 280);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [runWarehouseLookup, warehouseQuery]);

  return {
    applySettlementLookup,
    applyStreetLookup,
    applyWarehouseLookup,
    runStreetLookup,
  };
}
