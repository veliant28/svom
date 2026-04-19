"use client";

import { CarFront } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { VehicleSelectorModal } from "@/features/garage/components/modal/vehicle-selector-modal";
import { useActiveVehicle } from "@/features/garage/hooks/use-active-vehicle";
import { HeaderIconButton } from "@/shared/components/layout/header/header-icon-control";

export function GarageHeaderControl() {
  const t = useTranslations("common.header");
  const { isVehicleFilterActive, activeVehicleSource } = useActiveVehicle();
  const [isOpen, setIsOpen] = useState(false);

  const isActive = isVehicleFilterActive || isOpen;
  const badgeValue = isVehicleFilterActive ? 1 : 0;

  return (
    <>
      <HeaderIconButton
        tooltip={t("tooltips.garage")}
        icon={<CarFront size={18} />}
        onClick={() => setIsOpen(true)}
        isActive={isActive}
        badge={badgeValue}
        badgeTone="indigo"
        className={activeVehicleSource !== "none" ? "header-control-vehicle-filter" : ""}
      />
      {isOpen ? <VehicleSelectorModal isOpen={isOpen} onClose={() => setIsOpen(false)} /> : null}
    </>
  );
}
