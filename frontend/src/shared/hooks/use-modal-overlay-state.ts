"use client";

import { useEffect, useState } from "react";

type ModalLockState = {
  count: number;
  previousBodyOverflow: string;
  previousBodyPaddingRight: string;
};

type ModalLockChangeDetail = {
  count: number;
  isOpen: boolean;
};

const MODAL_OPEN_CLASS = "modal-open";
const MODAL_LOCK_CHANGE_EVENT = "svom:modal-lock-change";

declare global {
  interface Window {
    __svomModalLockState?: ModalLockState;
  }
}

function getModalLockState(): ModalLockState {
  if (typeof window === "undefined") {
    return {
      count: 0,
      previousBodyOverflow: "",
      previousBodyPaddingRight: "",
    };
  }

  if (!window.__svomModalLockState) {
    window.__svomModalLockState = {
      count: 0,
      previousBodyOverflow: "",
      previousBodyPaddingRight: "",
    };
  }

  return window.__svomModalLockState;
}

function emitModalLockChange(count: number): void {
  if (typeof window === "undefined") {
    return;
  }

  const detail: ModalLockChangeDetail = {
    count,
    isOpen: count > 0,
  };
  window.dispatchEvent(new CustomEvent<ModalLockChangeDetail>(MODAL_LOCK_CHANGE_EVENT, { detail }));
}

function applyBodyLock(state: ModalLockState): void {
  if (typeof document === "undefined") {
    return;
  }

  const body = document.body;
  const html = document.documentElement;
  state.previousBodyOverflow = body.style.overflow;
  state.previousBodyPaddingRight = body.style.paddingRight;

  const scrollbarWidth = Math.max(window.innerWidth - html.clientWidth, 0);
  body.style.overflow = "hidden";
  if (scrollbarWidth > 0) {
    body.style.paddingRight = `${scrollbarWidth}px`;
  }

  html.classList.add(MODAL_OPEN_CLASS);
  body.classList.add(MODAL_OPEN_CLASS);
}

function releaseBodyLock(state: ModalLockState): void {
  if (typeof document === "undefined") {
    return;
  }

  const body = document.body;
  const html = document.documentElement;

  body.style.overflow = state.previousBodyOverflow;
  body.style.paddingRight = state.previousBodyPaddingRight;
  html.classList.remove(MODAL_OPEN_CLASS);
  body.classList.remove(MODAL_OPEN_CLASS);
}

function isAnyModalOpenFromDom(): boolean {
  if (typeof document === "undefined") {
    return false;
  }
  return document.documentElement.classList.contains(MODAL_OPEN_CLASS) || document.body.classList.contains(MODAL_OPEN_CLASS);
}

export function acquireModalOverlayLock(): () => void {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return () => {};
  }

  const state = getModalLockState();
  state.count += 1;
  if (state.count === 1) {
    applyBodyLock(state);
  }
  emitModalLockChange(state.count);

  let released = false;
  return () => {
    if (released) {
      return;
    }
    released = true;

    const currentState = getModalLockState();
    currentState.count = Math.max(currentState.count - 1, 0);
    if (currentState.count === 0) {
      releaseBodyLock(currentState);
    }
    emitModalLockChange(currentState.count);
  };
}

export function useModalBodyLock(isOpen: boolean): void {
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const release = acquireModalOverlayLock();
    return release;
  }, [isOpen]);
}

export function useGlobalModalOpen(): boolean {
  const [isOpen, setIsOpen] = useState<boolean>(() => isAnyModalOpenFromDom());

  useEffect(() => {
    const updateFromDom = () => {
      setIsOpen(isAnyModalOpenFromDom());
    };

    const onLockChange = (event: Event) => {
      const customEvent = event as CustomEvent<ModalLockChangeDetail>;
      if (typeof customEvent.detail?.isOpen === "boolean") {
        setIsOpen(customEvent.detail.isOpen);
        return;
      }
      updateFromDom();
    };

    window.addEventListener(MODAL_LOCK_CHANGE_EVENT, onLockChange);
    updateFromDom();
    return () => {
      window.removeEventListener(MODAL_LOCK_CHANGE_EVENT, onLockChange);
    };
  }, []);

  return isOpen;
}
