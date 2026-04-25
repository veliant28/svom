import { useEffect, useMemo, useRef, type Dispatch, type SetStateAction } from "react";

import {
  resolveEffectiveSenderType,
  resolveSenderPaymentCapabilities,
  resolveSenderPreview,
} from "@/features/backoffice/components/orders/order-waybill-party.helpers";
import type { Translator } from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import { canSaveWaybill, type WaybillFormPayload } from "@/features/backoffice/lib/orders/waybill-form";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import type {
  BackofficeNovaPoshtaSenderProfile,
  BackofficeOrderNovaPoshtaWaybill,
} from "@/features/backoffice/types/nova-poshta.types";

export function useOrderWaybillPaymentState({
  isOpen,
  payload,
  setPayload,
  sender,
  waybill,
  recipientIsPrivatePerson,
  formDisabled,
  preferredDeliveryDateInvalid,
  t,
}: {
  isOpen: boolean;
  payload: WaybillFormPayload;
  setPayload: Dispatch<SetStateAction<WaybillFormPayload>>;
  sender: BackofficeNovaPoshtaSenderProfile | undefined;
  waybill: BackofficeOrderNovaPoshtaWaybill | null;
  recipientIsPrivatePerson: boolean;
  formDisabled: boolean;
  preferredDeliveryDateInvalid: boolean;
  t: Translator;
}) {
  const { showInfo } = useBackofficeFeedback();
  const lastPaymentWarningToastRef = useRef("");
  const senderPaymentCapabilities = useMemo(
    () => resolveSenderPaymentCapabilities(sender),
    [sender],
  );
  const effectiveSenderType = resolveEffectiveSenderType(sender, waybill?.sender_profile_type || "");
  const senderRequiresControlPayment = effectiveSenderType === "fop" || effectiveSenderType === "business";
  const controlPaymentSupported = senderPaymentCapabilities.canAfterpaymentOnGoodsCost !== false;
  const nonCashSupported = senderPaymentCapabilities.canNonCashPayment !== false;
  const thirdPersonSupported = senderPaymentCapabilities.canPayThirdPerson !== false && nonCashSupported;

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setPayload((prev) => {
      let nextPayerType = (prev.payer_type || "Recipient") as "Sender" | "Recipient" | "ThirdPerson";
      let nextPaymentMethod = (prev.payment_method || "Cash") as "Cash" | "NonCash";

      if (nextPayerType === "ThirdPerson" && !thirdPersonSupported) {
        nextPayerType = "Recipient";
      }
      if (nextPayerType === "ThirdPerson" && nextPaymentMethod !== "NonCash") {
        nextPaymentMethod = "NonCash";
      }
      if (nextPayerType === "Recipient" && recipientIsPrivatePerson && nextPaymentMethod === "NonCash") {
        nextPaymentMethod = "Cash";
      }
      if (nextPaymentMethod === "NonCash" && !nonCashSupported) {
        nextPaymentMethod = "Cash";
      }

      if (nextPayerType === prev.payer_type && nextPaymentMethod === prev.payment_method) {
        return prev;
      }
      return {
        ...prev,
        payer_type: nextPayerType,
        payment_method: nextPaymentMethod,
      };
    });
  }, [isOpen, nonCashSupported, recipientIsPrivatePerson, setPayload, thirdPersonSupported]);

  const senderPreview = resolveSenderPreview();
  const payerTypeUi = (payload.payer_type || waybill?.payer_type || senderPreview.payer || "Recipient") as "Sender" | "Recipient" | "ThirdPerson";
  const paymentMethodUi = (payload.payment_method || waybill?.payment_method || senderPreview.payment || "Cash") as "Cash" | "NonCash";
  const paymentAmountFieldLabel = senderRequiresControlPayment
    ? t("orders.modals.waybill.additional.controlPaymentAmount")
    : t("orders.modals.waybill.additional.cashOnDeliveryAmount");

  let paymentValidationMessage = "";
  if (payerTypeUi === "ThirdPerson" && !thirdPersonSupported) {
    paymentValidationMessage = t("orders.modals.waybill.meta.validation.thirdPersonUnavailable");
  } else if (paymentMethodUi === "NonCash" && !nonCashSupported) {
    paymentValidationMessage = t("orders.modals.waybill.meta.validation.nonCashUnavailable");
  } else if (payerTypeUi === "Recipient" && recipientIsPrivatePerson && paymentMethodUi === "NonCash") {
    paymentValidationMessage = t("orders.modals.waybill.meta.validation.nonCashUnavailableForPrivateRecipient");
  } else if (payerTypeUi === "ThirdPerson" && paymentMethodUi !== "NonCash") {
    paymentValidationMessage = t("orders.modals.waybill.meta.validation.thirdPersonRequiresNonCash");
  }

  const controlPaymentWarningMessage = senderRequiresControlPayment && !controlPaymentSupported
    ? t("orders.modals.waybill.meta.validation.controlPaymentUnavailable")
    : "";

  useEffect(() => {
    if (!isOpen) {
      lastPaymentWarningToastRef.current = "";
      return;
    }
    if (!controlPaymentWarningMessage) {
      lastPaymentWarningToastRef.current = "";
      return;
    }
    if (lastPaymentWarningToastRef.current === controlPaymentWarningMessage) {
      return;
    }
    showInfo(controlPaymentWarningMessage);
    lastPaymentWarningToastRef.current = controlPaymentWarningMessage;
  }, [controlPaymentWarningMessage, isOpen, showInfo]);

  return {
    nonCashSupported,
    thirdPersonSupported,
    payerTypeUi,
    paymentMethodUi,
    paymentAmountFieldLabel,
    paymentValidationMessage,
    canSubmit: canSaveWaybill(payload) && !formDisabled && !paymentValidationMessage && !preferredDeliveryDateInvalid,
  };
}
