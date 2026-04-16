"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useSyncExternalStore } from "react";
import type { ReactNode } from "react";

export type BackofficeHeaderConfig = {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  actionsBeforeLogout?: ReactNode;
  switcher?: ReactNode;
};

type BackofficeHeaderContextValue = {
  setConfig: (next: BackofficeHeaderConfig) => void;
  clearConfig: () => void;
};

const EMPTY_CONFIG: BackofficeHeaderConfig = {};

type BackofficeHeaderStore = {
  getSnapshot: () => BackofficeHeaderConfig;
  subscribe: (listener: () => void) => () => void;
  setConfig: (next: BackofficeHeaderConfig) => void;
  clearConfig: () => void;
};

function createHeaderStore(): BackofficeHeaderStore {
  let config = EMPTY_CONFIG;
  const listeners = new Set<() => void>();

  const notify = () => {
    for (const listener of listeners) {
      listener();
    }
  };

  return {
    getSnapshot: () => config,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    setConfig: (next) => {
      config = next;
      notify();
    },
    clearConfig: () => {
      config = EMPTY_CONFIG;
      notify();
    },
  };
}

const BackofficeHeaderStoreContext = createContext<BackofficeHeaderStore | null>(null);
const BackofficeHeaderDispatchContext = createContext<BackofficeHeaderContextValue | null>(null);

export function BackofficeHeaderProvider({ children }: { children: ReactNode }) {
  const storeRef = useRef<BackofficeHeaderStore | null>(null);
  if (!storeRef.current) {
    storeRef.current = createHeaderStore();
  }
  const store = storeRef.current;

  const setConfig = useCallback((next: BackofficeHeaderConfig) => {
    store.setConfig(next);
  }, [store]);

  const clearConfig = useCallback(() => {
    store.clearConfig();
  }, [store]);

  return (
    <BackofficeHeaderDispatchContext.Provider value={{ setConfig, clearConfig }}>
      <BackofficeHeaderStoreContext.Provider value={store}>{children}</BackofficeHeaderStoreContext.Provider>
    </BackofficeHeaderDispatchContext.Provider>
  );
}

export function useBackofficeHeaderConfig() {
  const store = useContext(BackofficeHeaderStoreContext);
  if (!store) {
    throw new Error("useBackofficeHeaderConfig must be used within BackofficeHeaderProvider");
  }
  return useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
}

function useBackofficeHeaderDispatch() {
  const context = useContext(BackofficeHeaderDispatchContext);
  if (!context) {
    throw new Error("useBackofficeHeaderDispatch must be used within BackofficeHeaderProvider");
  }
  return context;
}

export function useBackofficeHeader(config: BackofficeHeaderConfig) {
  const { setConfig, clearConfig } = useBackofficeHeaderDispatch();

  useEffect(() => {
    setConfig(config);
  }, [config.actions, config.actionsBeforeLogout, config.subtitle, config.switcher, config.title, setConfig]);

  useEffect(
    () => () => {
      clearConfig();
    },
    [clearConfig],
  );
}
