import {
  Archive,
  ArrowLeft,
  Circle,
  FileText,
  MoreHorizontal,
  Truck,
} from "lucide-react";
import type { Dispatch, MutableRefObject, RefObject, SetStateAction } from "react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import type { Translator } from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import type {
  WaybillFormPayload,
  WaybillSeatOptionPayload,
} from "@/features/backoffice/lib/orders/waybill-form";
import type { BackofficeNovaPoshtaLookupPackaging } from "@/features/backoffice/types/nova-poshta.types";

type CargoTypeUi = "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels";
type SelectableCargoType = "Cargo" | "Parcel" | "Documents" | "Pallet";

type UpdateSeatOptions = (
  updater: (seats: WaybillSeatOptionPayload[], activeIndex: number) => WaybillSeatOptionPayload[],
) => void;

export function OrderWaybillShipmentSection({
  seatMenuRef,
  seatListButtonsRef,
  packingsLookupRootRef,
  packingsInputRef,
  isPackagingMode,
  isSeatListMode,
  seatMenuOpen,
  selectedSeatIndex,
  normalizedSeatsAmount,
  seatOptions,
  activeSeat,
  selectedPackingsDisplay,
  packingsLoading,
  visiblePackings,
  hasSelectedPackings,
  packagingWidth,
  packagingLength,
  packagingHeight,
  volumetricWeight,
  cargoTypeUi,
  formDisabled,
  t,
  setIsSeatListMode,
  setSeatMenuOpen,
  setSelectedSeatIndex,
  setPackingsDropdownOpen,
  setPackagingWidth,
  setPackagingLength,
  setPackagingHeight,
  setIsPackagingEnabled,
  leavePackagingMode,
  addSeat,
  removeSeat,
  enterSeatListMode,
  openSeatForEditing,
  updateSeatOptions,
  enterPackagingMode,
  applyCargoTypeSelection,
}: {
  seatMenuRef: RefObject<HTMLDivElement | null>;
  seatListButtonsRef: MutableRefObject<Array<HTMLButtonElement | null>>;
  packingsLookupRootRef: RefObject<HTMLLabelElement | null>;
  packingsInputRef: RefObject<HTMLInputElement | null>;
  isPackagingMode: boolean;
  isSeatListMode: boolean;
  seatMenuOpen: boolean;
  selectedSeatIndex: number;
  normalizedSeatsAmount: number;
  seatOptions: WaybillSeatOptionPayload[];
  activeSeat: WaybillSeatOptionPayload;
  selectedPackingsDisplay: string;
  packingsLoading: boolean;
  visiblePackings: BackofficeNovaPoshtaLookupPackaging[];
  hasSelectedPackings: boolean;
  packagingWidth: string;
  packagingLength: string;
  packagingHeight: string;
  volumetricWeight: string;
  cargoTypeUi: CargoTypeUi;
  formDisabled: boolean;
  t: Translator;
  setIsSeatListMode: Dispatch<SetStateAction<boolean>>;
  setSeatMenuOpen: Dispatch<SetStateAction<boolean>>;
  setSelectedSeatIndex: Dispatch<SetStateAction<number>>;
  setPackingsDropdownOpen: Dispatch<SetStateAction<boolean>>;
  setPackagingWidth: Dispatch<SetStateAction<string>>;
  setPackagingLength: Dispatch<SetStateAction<string>>;
  setPackagingHeight: Dispatch<SetStateAction<string>>;
  setIsPackagingEnabled: Dispatch<SetStateAction<boolean>>;
  leavePackagingMode: () => void;
  addSeat: () => void;
  removeSeat: () => void;
  enterSeatListMode: () => void;
  openSeatForEditing: (index: number) => void;
  updateSeatOptions: UpdateSeatOptions;
  enterPackagingMode: () => void;
  applyCargoTypeSelection: (nextType: SelectableCargoType) => void;
}) {
  const cargoButtons: Array<{
    value: SelectableCargoType;
    labelKey: string;
    icon: typeof FileText;
  }> = [
    { value: "Documents", labelKey: "documents", icon: FileText },
    { value: "Parcel", labelKey: "parcel", icon: Archive },
    { value: "Cargo", labelKey: "cargo", icon: Truck },
    { value: "Pallet", labelKey: "pallet", icon: Circle },
  ];

  return (
    <section
      className="order-2 rounded-md border p-3 xl:h-[460px] xl:overflow-y-auto"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <div className="flex h-8 items-center justify-between gap-2">
        <div className="flex min-w-0 items-baseline gap-2">
          <h3 className="text-foreground whitespace-nowrap text-sm font-semibold">{t("orders.modals.waybill.sectionShipment")}</h3>
          <span className="truncate whitespace-nowrap text-xs" style={{ color: "var(--muted)" }}>
            {t("orders.modals.waybill.fields.seats")}: {selectedSeatIndex + 1}/{normalizedSeatsAmount}
          </span>
        </div>
        {isPackagingMode || isSeatListMode ? (
          <button
            type="button"
            className="inline-flex h-8 items-center justify-center gap-1 rounded-md border px-2.5 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
            onClick={() => {
              setIsSeatListMode(false);
              leavePackagingMode();
            }}
            disabled={formDisabled}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>{isSeatListMode ? t("orders.modals.waybill.actions.backFromSeatList") : t("orders.modals.waybill.actions.backFromPackaging")}</span>
          </button>
        ) : (
          <div ref={seatMenuRef} className="relative">
            <button
              type="button"
              className="inline-flex h-8 cursor-pointer items-center justify-center rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
              aria-label={t("orders.modals.waybill.fields.seats")}
              onClick={() => setSeatMenuOpen((prev) => !prev)}
              disabled={formDisabled}
            >
              <MoreHorizontal className="size-4 stroke-[2.5]" />
            </button>
            {seatMenuOpen ? (
              <div
                className="absolute right-0 top-[calc(100%+0.35rem)] z-[100] min-w-56 rounded-md border p-1.5 shadow-lg"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
              >
                <button
                  type="button"
                  className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100/70 dark:hover:bg-slate-700/40"
                  onClick={addSeat}
                >
                  {t("orders.modals.waybill.actions.addSeat")}
                </button>
                {normalizedSeatsAmount > 1 ? (
                  <button
                    type="button"
                    className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100/70 dark:hover:bg-slate-700/40"
                    onClick={removeSeat}
                  >
                    {t("orders.modals.waybill.actions.removeSeat")}
                  </button>
                ) : null}
                {normalizedSeatsAmount > 1 ? (
                  <>
                    <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
                    <button
                      type="button"
                      className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100/70 dark:hover:bg-slate-700/40"
                      onClick={enterSeatListMode}
                    >
                      {t("orders.modals.waybill.actions.seatList")}
                    </button>
                  </>
                ) : null}
                <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
                <p className="px-2 py-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("orders.modals.waybill.fields.seats")}: {normalizedSeatsAmount}
                </p>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {isSeatListMode ? (
        <div className="grid gap-2 pt-0.5">
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            {t("orders.modals.waybill.actions.seatList")}
          </p>
          <div
            className="grid gap-2"
            role="listbox"
            aria-label={t("orders.modals.waybill.actions.seatList")}
            onKeyDown={(event) => {
              if (!seatOptions.length) {
                return;
              }
              if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
                return;
              }
              event.preventDefault();
              const direction = event.key === "ArrowDown" ? 1 : -1;
              const current = selectedSeatIndex;
              const next = Math.max(0, Math.min(current + direction, seatOptions.length - 1));
              setSelectedSeatIndex(next);
              seatListButtonsRef.current[next]?.focus();
            }}
          >
            {seatOptions.map((seat, index) => (
              <button
                key={`seat-list-${index}`}
                ref={(node) => {
                  seatListButtonsRef.current[index] = node;
                }}
                type="button"
                className="rounded-md border px-3 py-2 text-left text-sm"
                style={{
                  borderColor: selectedSeatIndex === index ? "#2563eb" : "var(--border)",
                  backgroundColor: selectedSeatIndex === index ? "rgba(37,99,235,0.08)" : "var(--surface-2)",
                }}
                role="option"
                aria-selected={selectedSeatIndex === index}
                onClick={() => openSeatForEditing(index)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openSeatForEditing(index);
                  }
                }}
              >
                <p className="font-semibold">
                  {t("orders.modals.waybill.actions.seatCardTitle", { index: index + 1 })}
                </p>
                <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
                  {t("orders.modals.waybill.fields.weight")}: {seat.weight || "-"}
                </p>
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {t("orders.modals.waybill.fields.cost")}: {seat.cost || "-"}
                </p>
              </button>
            ))}
          </div>
        </div>
      ) : isPackagingMode ? (
        <div className="grid gap-1 pt-0.5">
          <label ref={packingsLookupRootRef} className="grid min-w-0 gap-1 text-xs">
            <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.packRef")}</span>
            <input
              ref={packingsInputRef}
              className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              value={selectedPackingsDisplay}
              placeholder={t("orders.modals.waybill.fields.packRefHint")}
              disabled={formDisabled}
              readOnly
              onFocus={() => setPackingsDropdownOpen(true)}
              onClick={() => setPackingsDropdownOpen(true)}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setPackingsDropdownOpen(false);
                }
              }}
            />
            <span className="text-[11px]" style={{ color: "var(--muted)" }}>
              {t("orders.modals.waybill.fields.packRefHint")}
            </span>
            {packingsLoading ? (
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                {t("orders.modals.waybill.fields.packRefLoading")}
              </p>
            ) : null}
            {!packingsLoading && !visiblePackings.length ? (
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                {t("orders.modals.waybill.fields.packRefEmpty")}
              </p>
            ) : null}
          </label>
        </div>
      ) : (
        <div className="grid gap-1 pt-0.5">
          <label className="grid gap-1 text-xs">
            <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.description")}</span>
            <input
              className="h-10 rounded-md border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              value={activeSeat.description || ""}
              disabled={formDisabled}
              onChange={(event) => updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                index === activeIndex ? { ...seat, description: event.target.value } : seat
              )))}
            />
          </label>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 sm:items-end">
            <label className="grid min-w-0 gap-1 text-xs">
              <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.cost")}</span>
              <input
                className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                value={activeSeat.cost || ""}
                disabled={formDisabled}
                onChange={(event) => updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                  index === activeIndex ? { ...seat, cost: event.target.value } : seat
                )))}
              />
            </label>
            <label className="grid min-w-0 gap-1 text-xs">
              <span className="truncate" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.weight")}</span>
              <input
                className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                value={activeSeat.weight || ""}
                disabled={formDisabled}
                onChange={(event) => updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                  index === activeIndex ? { ...seat, weight: event.target.value } : seat
                )))}
              />
            </label>
          </div>

          <div className="grid gap-1">
            <span aria-hidden="true" className="text-xs opacity-0">.</span>
            <button
              type="button"
              className="h-10 rounded-md border px-3 text-sm font-semibold"
              style={{
                borderColor: hasSelectedPackings ? "#3f8a5a" : "#2563eb",
                backgroundColor: hasSelectedPackings ? "#4b9264" : "#2563eb",
                color: hasSelectedPackings ? "#f7fffa" : "#fff",
              }}
              disabled={formDisabled}
              onClick={enterPackagingMode}
            >
              {hasSelectedPackings
                ? t("orders.modals.waybill.actions.packagingAdded")
                : t("orders.modals.waybill.actions.addPackaging")}
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
            {[
              ["widthCm", packagingWidth, setPackagingWidth, "volumetric_width"],
              ["lengthCm", packagingLength, setPackagingLength, "volumetric_length"],
              ["heightCm", packagingHeight, setPackagingHeight, "volumetric_height"],
            ].map(([key, value, setter, field]) => (
              <label key={String(field)} className="grid min-w-0 gap-1 text-xs">
                <span className="truncate" style={{ color: "var(--muted)" }}>{t(`orders.modals.waybill.fields.${key}`)}</span>
                <input
                  className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  value={String(value)}
                  disabled={formDisabled}
                  onChange={(event) => {
                    const nextValue = event.target.value;
                    (setter as Dispatch<SetStateAction<string>>)(nextValue);
                    setIsPackagingEnabled(true);
                    updateSeatOptions((seats, activeIndex) => seats.map((seat, index) => (
                      index === activeIndex
                        ? { ...seat, [field as keyof WaybillFormPayload]: nextValue }
                        : seat
                    )));
                  }}
                />
              </label>
            ))}
          </div>

          <div className="grid gap-1">
            <span aria-hidden="true" className="text-xs opacity-0">.</span>
            <div
              className="rounded-md flex h-10 min-w-0 items-center justify-center gap-2 border px-3 text-sm text-center"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            >
              <span className="font-semibold text-[var(--text)]">
                {t("orders.modals.waybill.fields.volumetricWeight")}
              </span>
              <span style={{ color: "var(--muted)" }}>
                {volumetricWeight} {t("orders.modals.waybill.fields.weightUnit")}
              </span>
            </div>
          </div>

          <div className="grid gap-1">
            <span aria-hidden="true" className="text-xs opacity-0">.</span>
            <div className="flex items-center justify-center gap-2">
              {cargoButtons.map(({ value, labelKey, icon: Icon }) => (
                <BackofficeTooltip
                  key={value}
                  content={t(`orders.modals.waybill.cargoTypes.${labelKey}`)}
                  placement="bottom"
                  align="center"
                  wrapperClassName="inline-flex"
                >
                  <button
                    type="button"
                    className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
                    style={{
                      borderColor: cargoTypeUi === value ? "#2563eb" : "var(--border)",
                      backgroundColor: cargoTypeUi === value ? "#2563eb" : "var(--surface-2)",
                      color: cargoTypeUi === value ? "#fff" : "var(--muted)",
                    }}
                    disabled={formDisabled}
                    onClick={() => applyCargoTypeSelection(value)}
                  >
                    <Icon className="h-4 w-4" />
                  </button>
                </BackofficeTooltip>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
