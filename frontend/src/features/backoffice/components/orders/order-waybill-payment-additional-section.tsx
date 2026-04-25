import { AlertCircle, ArrowLeft } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";

import {
  formatPreferredDeliveryDateInput,
  normalizePreferredDeliveryDate,
  type Translator,
} from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import {
  resolvePayerTypeLabel,
  resolvePaymentMethodLabel,
} from "@/features/backoffice/components/orders/order-waybill-party.helpers";
import type { WaybillFormPayload } from "@/features/backoffice/lib/orders/waybill-form";
import type { BackofficeNovaPoshtaLookupDeliveryDate } from "@/features/backoffice/types/nova-poshta.types";

type PayerType = "Sender" | "Recipient" | "ThirdPerson";
type PaymentMethod = "Cash" | "NonCash";

type TimeIntervalOption = {
  value: string;
  label: string;
};

export function OrderWaybillPaymentAdditionalSection({
  isAdditionalServicesMode,
  formDisabled,
  payload,
  currency,
  paymentAmountFieldLabel,
  payerTypeUi,
  paymentMethodUi,
  thirdPersonSupported,
  recipientIsPrivatePerson,
  nonCashSupported,
  paymentValidationMessage,
  preferredDeliveryDateInvalid,
  deliveryDateLookupLoading,
  deliveryDateLookup,
  timeIntervalsLoading,
  timeIntervalOptions,
  syncError,
  t,
  setPayload,
  applyPayerTypeSelection,
  applyPaymentMethodSelection,
  enterAdditionalServicesMode,
  leaveAdditionalServicesMode,
}: {
  isAdditionalServicesMode: boolean;
  formDisabled: boolean;
  payload: WaybillFormPayload;
  currency: string;
  paymentAmountFieldLabel: string;
  payerTypeUi: PayerType;
  paymentMethodUi: PaymentMethod;
  thirdPersonSupported: boolean;
  recipientIsPrivatePerson: boolean;
  nonCashSupported: boolean;
  paymentValidationMessage: string;
  preferredDeliveryDateInvalid: boolean;
  deliveryDateLookupLoading: boolean;
  deliveryDateLookup: BackofficeNovaPoshtaLookupDeliveryDate | null;
  timeIntervalsLoading: boolean;
  timeIntervalOptions: TimeIntervalOption[];
  syncError: string;
  t: Translator;
  setPayload: Dispatch<SetStateAction<WaybillFormPayload>>;
  applyPayerTypeSelection: (value: PayerType) => void;
  applyPaymentMethodSelection: (value: PaymentMethod) => void;
  enterAdditionalServicesMode: () => void;
  leaveAdditionalServicesMode: () => void;
}) {
  return (
    <section
      className={`${isAdditionalServicesMode ? "order-3 xl:col-span-2" : "order-4"} rounded-md border p-3 xl:h-[460px] xl:overflow-y-auto`}
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <div className="flex h-8 items-center justify-between gap-2">
        <h3 className="text-foreground whitespace-nowrap text-sm font-semibold">
          {isAdditionalServicesMode
            ? t("orders.modals.waybill.actions.additionalServices")
            : t("orders.modals.waybill.sectionPaymentAdditional")}
        </h3>
        {isAdditionalServicesMode ? (
          <button
            type="button"
            className="inline-flex h-8 cursor-pointer items-center justify-center gap-1 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
            onClick={leaveAdditionalServicesMode}
            disabled={formDisabled}
          >
            <ArrowLeft className="size-4 stroke-[2.5]" />
            <span>{t("orders.modals.waybill.actions.backFromAdditionalServices")}</span>
          </button>
        ) : null}
      </div>

      <div className="grid gap-1 pt-0.5">
        {!isAdditionalServicesMode ? (
          <>
            <div className="grid gap-1 pb-1">
              <span className="text-xs opacity-0" style={{ color: "var(--muted)" }} aria-hidden>
                {t("orders.modals.waybill.fields.cost")}
              </span>
              <div className="grid min-h-[96px] min-w-0 content-start gap-1 rounded-md border px-3 py-1.5 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <span className="min-w-0 font-medium" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.payment.toPay")}</span>
                  <span className="shrink-0 font-semibold">—</span>
                </div>
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <span className="min-w-0 font-medium" style={{ color: "var(--muted)" }}>{paymentAmountFieldLabel}</span>
                  <span className="shrink-0 font-semibold">{payload.afterpayment_amount || "0"} {currency}</span>
                </div>
              </div>
            </div>

            <div className="mt-1 grid gap-1">
              <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.meta.payerType")}</span>
              <div className="grid gap-2 sm:grid-cols-3">
                {(["Sender", "Recipient", "ThirdPerson"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    className="h-10 rounded-md border px-4 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                    style={{
                      borderColor: payerTypeUi === value ? "#2563eb" : "var(--border)",
                      backgroundColor: payerTypeUi === value ? "#2563eb" : "var(--surface)",
                      color: payerTypeUi === value ? "#fff" : "var(--text)",
                    }}
                    disabled={formDisabled || (value === "ThirdPerson" && !thirdPersonSupported)}
                    onClick={() => applyPayerTypeSelection(value)}
                  >
                    {resolvePayerTypeLabel(value, t)}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-1">
              <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.meta.paymentMethod")}</span>
              <div className="grid gap-2 sm:grid-cols-2">
                {(["Cash", "NonCash"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    className="h-10 rounded-md border px-4 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                    style={{
                      borderColor: paymentMethodUi === value ? "#2563eb" : "var(--border)",
                      backgroundColor: paymentMethodUi === value ? "#2563eb" : "var(--surface)",
                      color: paymentMethodUi === value ? "#fff" : "var(--text)",
                    }}
                    disabled={
                      formDisabled
                      || (payerTypeUi === "ThirdPerson" && value === "Cash")
                      || (payerTypeUi === "Recipient" && recipientIsPrivatePerson && value === "NonCash")
                      || (value === "NonCash" && !nonCashSupported)
                    }
                    onClick={() => applyPaymentMethodSelection(value)}
                  >
                    {resolvePaymentMethodLabel(value, t)}
                  </button>
                ))}
              </div>
            </div>
            {paymentValidationMessage ? (
              <div
                className="rounded-md border px-2 py-1.5 text-xs"
                style={{ borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,.12)", color: "#92400e" }}
              >
                {paymentValidationMessage}
              </div>
            ) : null}
          </>
        ) : null}

        {isAdditionalServicesMode ? (
          <div className="grid gap-1 md:grid-cols-2 xl:grid-cols-3">
            <label className="grid min-w-0 gap-1 text-xs">
              <span style={{ color: "var(--muted)" }}>{paymentAmountFieldLabel}</span>
              <input
                className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                value={payload.afterpayment_amount || ""}
                disabled={formDisabled}
                onChange={(event) => setPayload((prev) => ({ ...prev, afterpayment_amount: event.target.value }))}
              />
            </label>
            <label className="grid min-w-0 gap-1 text-xs">
              <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.infoRegClientBarcodes")}</span>
              <input
                className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                value={payload.info_reg_client_barcodes || ""}
                disabled={formDisabled}
                onChange={(event) => setPayload((prev) => ({ ...prev, info_reg_client_barcodes: event.target.value }))}
              />
            </label>

            {[
              ["saturday_delivery", "saturdayDelivery"],
              ["local_express", "localExpress"],
              ["delivery_by_hand", "deliveryByHand"],
              ["special_cargo", "specialCargo"],
            ].map(([field, key]) => (
              <label key={field} className="grid min-w-0 gap-1 text-xs">
                <span style={{ color: "var(--muted)" }}>{t(`orders.modals.waybill.additional.${key}`)}</span>
                <div
                  className="flex h-10 w-full min-w-0 items-center rounded-md border px-3 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                >
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={Boolean(payload[field as keyof WaybillFormPayload])}
                      disabled={formDisabled}
                      onChange={(event) => setPayload((prev) => ({ ...prev, [field]: event.target.checked }))}
                    />
                    <span className="font-semibold">{t(`orders.modals.waybill.additional.${key}`)}</span>
                  </label>
                </div>
              </label>
            ))}

            <label className="grid min-w-0 gap-1 text-xs">
              <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.preferredDeliveryDate")}</span>
              <input
                className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                style={{
                  borderColor: preferredDeliveryDateInvalid ? "#ef4444" : "var(--border)",
                  backgroundColor: "var(--surface-2)",
                }}
                value={payload.preferred_delivery_date || ""}
                disabled={formDisabled || deliveryDateLookupLoading}
                placeholder={deliveryDateLookup?.date || t("orders.modals.waybill.additional.datePlaceholder")}
                inputMode="numeric"
                maxLength={10}
                onChange={(event) => setPayload((prev) => ({
                  ...prev,
                  preferred_delivery_date: formatPreferredDeliveryDateInput(event.target.value),
                }))}
                onBlur={() => setPayload((prev) => ({
                  ...prev,
                  preferred_delivery_date: normalizePreferredDeliveryDate(prev.preferred_delivery_date || ""),
                }))}
              />
            </label>
            <label className="grid min-w-0 gap-1 text-xs">
              <span style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.additional.timeInterval")}</span>
              <select
                className="h-10 w-full min-w-0 rounded-md border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                value={payload.time_interval || ""}
                disabled={formDisabled || !payload.recipient_city_ref || timeIntervalsLoading}
                onChange={(event) => {
                  const value = event.target.value as WaybillFormPayload["time_interval"];
                  setPayload((prev) => ({ ...prev, time_interval: value }));
                }}
              >
                <option value="">{t("orders.modals.waybill.additional.timeIntervalNone")}</option>
                {timeIntervalOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            {[
              ["accompanying_documents", "accompanyingDocuments"],
              ["red_box_barcode", "redBoxBarcode"],
              ["forwarding_count", "forwardingCount"],
              ["number_of_floors_lifting", "numberOfFloorsLifting"],
              ["number_of_floors_descent", "numberOfFloorsDescent"],
            ].map(([field, key]) => (
              <label key={field} className="grid min-w-0 gap-1 text-xs">
                <span style={{ color: "var(--muted)" }}>{t(`orders.modals.waybill.additional.${key}`)}</span>
                <input
                  className={`h-10 w-full min-w-0 rounded-md border px-3 text-sm${field === "red_box_barcode" ? " uppercase" : ""}`}
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  value={String(payload[field as keyof WaybillFormPayload] || "")}
                  disabled={formDisabled}
                  onChange={(event) => setPayload((prev) => ({
                    ...prev,
                    [field]: field === "red_box_barcode" ? event.target.value.toUpperCase() : event.target.value,
                  }))}
                />
              </label>
            ))}
          </div>
        ) : (
          <button
            type="button"
            className="mt-5 h-10 rounded-md border px-3 text-sm font-medium"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
            disabled={formDisabled}
            onClick={enterAdditionalServicesMode}
          >
            {t("orders.modals.waybill.actions.additionalServices")}
          </button>
        )}

        {syncError ? (
          <div
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ borderColor: "#ef4444", backgroundColor: "rgba(239,68,68,.12)", color: "#991b1b" }}
          >
            <div className="flex items-start gap-1.5">
              <AlertCircle className="mt-0.5 h-3.5 w-3.5" />
              <span className="leading-4">{syncError}</span>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
