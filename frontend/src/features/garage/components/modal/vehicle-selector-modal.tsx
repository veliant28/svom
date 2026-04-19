"use client";

import { CarFront, RefreshCw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";

import { SavedVehiclesSelector } from "@/features/garage/components/modal/saved-vehicles-selector";
import { NewVehicleSelectionForm } from "@/features/garage/components/modal/new-vehicle-selection-form";
import { useActiveVehicle } from "@/features/garage/hooks/use-active-vehicle";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { Link } from "@/i18n/navigation";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type VehicleSelectorModalProps = {
  isOpen: boolean;
  onClose: () => void;
};

type VehicleModalTab = "saved" | "new";

export function VehicleSelectorModal({ isOpen, onClose }: VehicleSelectorModalProps) {
  const t = useTranslations("common.header.vehicleModal");
  const { showError, showInfo, showSuccess } = useStorefrontFeedback();
  const { isAuthenticated } = useAuth();
  const {
    garageVehicles,
    isGarageLoading,
    garageError,
    refreshGarageVehicles,
    addVehicleToGarage,
    activeVehicleSource,
    activeGarageVehicleId,
    selectGarageVehicle,
    selectTemporaryVehicle,
    clearActiveVehicle,
  } = useActiveVehicle();
  const [activeTab, setActiveTab] = useState<VehicleModalTab>("saved");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      setActiveTab("saved");
    }
  }, [isOpen]);

  useEffect(() => {
    if (garageError) {
      showError(t("saved.states.error"));
    }
  }, [garageError, showError, t]);

  if (!isOpen || !isMounted) {
    return null;
  }

  const activeFromGarage = activeVehicleSource === "garage" ? activeGarageVehicleId : null;

  return createPortal(
    <div
      className="fixed inset-0 z-[90] flex items-start justify-center bg-black/35 px-3 pb-6 pt-[8vh] backdrop-blur-[1px]"
      onMouseDown={(event) => {
        if (!dialogRef.current?.contains(event.target as Node)) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        className="w-full max-w-3xl rounded-2xl border p-4 shadow-2xl"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        role="dialog"
        aria-modal="true"
        aria-label={t("title")}
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="inline-flex items-center gap-2 text-base font-semibold">
              <CarFront size={18} />
              {t("title")}
            </h2>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
              {t("subtitle")}
            </p>
          </div>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            aria-label={t("actions.close")}
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="h-9 rounded-lg border px-3 text-sm font-medium"
            style={{
              borderColor: activeTab === "saved" ? "var(--accent)" : "var(--border)",
              backgroundColor:
                activeTab === "saved" ? "color-mix(in srgb, var(--accent) 11%, var(--surface))" : "var(--surface)",
            }}
            onClick={() => setActiveTab("saved")}
          >
            {t("tabs.saved")}
          </button>
          <button
            type="button"
            className="h-9 rounded-lg border px-3 text-sm font-medium"
            style={{
              borderColor: activeTab === "new" ? "var(--accent)" : "var(--border)",
              backgroundColor:
                activeTab === "new" ? "color-mix(in srgb, var(--accent) 11%, var(--surface))" : "var(--surface)",
            }}
            onClick={() => setActiveTab("new")}
          >
            {t("tabs.new")}
          </button>
          {isAuthenticated ? (
            <Link
              href="/garage"
              className="inline-flex h-9 items-center rounded-lg border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={onClose}
            >
              {t("actions.openGarage")}
            </Link>
          ) : null}

          <button
            type="button"
            className="inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-sm disabled:opacity-60"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            disabled={isRefreshing}
            onClick={async () => {
              setIsRefreshing(true);
              try {
                await refreshGarageVehicles();
              } finally {
                setIsRefreshing(false);
              }
            }}
          >
            <RefreshCw
              size={14}
              className="animate-spin"
              style={{ animationDuration: "2.2s" }}
            />
            {t("actions.refresh")}
          </button>
        </div>

        <div className="mt-4 max-h-[62vh] overflow-y-auto pr-1">
          {activeTab === "saved" ? (
            <SavedVehiclesSelector
              vehicles={garageVehicles}
              isLoading={isGarageLoading}
              activeVehicleId={activeFromGarage}
              onUseVehicle={(vehicleId) => {
                selectGarageVehicle(vehicleId);
                showSuccess(t("saved.messages.usedForFiltering"));
                onClose();
              }}
              onClearActive={() => {
                clearActiveVehicle();
                showInfo(t("saved.messages.cleared"));
              }}
            />
          ) : (
            <NewVehicleSelectionForm
              isAuthenticated={isAuthenticated}
              onUseTemporary={(carModificationId) => {
                selectTemporaryVehicle(carModificationId);
              }}
              onSaveVehicle={async (payload) => {
                if (activeVehicleSource === "none") {
                  clearActiveVehicle({ manual: true });
                }
                await addVehicleToGarage(payload);
              }}
            />
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
