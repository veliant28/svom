import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from "react";

import { lookupBackofficeNovaPoshtaCounterpartyDetails } from "@/features/backoffice/api/orders-api";
import type { WaybillAddressSuggestion } from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import { resolveCounterpartyTypeDisplay } from "@/features/backoffice/components/orders/order-waybill-party.helpers";
import { normalizeWaybillPhone, type WaybillFormPayload } from "@/features/backoffice/lib/orders/waybill-form";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupStreet,
} from "@/features/backoffice/types/nova-poshta.types";

export function useOrderWaybillRecipientCounterpartySelection({
  token,
  locale,
  senderProfileId,
  recipientCounterpartyDetailsRequestRef,
  skipNextRecipientCounterpartyLookupRef,
  skipNextSettlementLookupRef,
  setPayload,
  setRecipientCounterpartyQuery,
  setRecipientCounterpartyTypeLabel,
  setRecipientCounterpartyTypeRaw,
  setRecipientCounterparties,
  setActiveRecipientCounterpartyIndex,
  setSelectedSettlementRef,
  setCityLookupInteracted,
  setCityQuery,
  setStreetQuery,
  setStreets,
  setActiveStreetIndex,
  setWarehouseQuery,
  setWarehouses,
  setActiveWarehouseIndex,
}: {
  token: string | null;
  locale: string;
  senderProfileId: string;
  recipientCounterpartyDetailsRequestRef: MutableRefObject<number>;
  skipNextRecipientCounterpartyLookupRef: MutableRefObject<boolean>;
  skipNextSettlementLookupRef: MutableRefObject<boolean>;
  setPayload: Dispatch<SetStateAction<WaybillFormPayload>>;
  setRecipientCounterpartyQuery: Dispatch<SetStateAction<string>>;
  setRecipientCounterpartyTypeLabel: Dispatch<SetStateAction<string>>;
  setRecipientCounterpartyTypeRaw: Dispatch<SetStateAction<string>>;
  setRecipientCounterparties: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupCounterparty[]>>;
  setActiveRecipientCounterpartyIndex: Dispatch<SetStateAction<number>>;
  setSelectedSettlementRef: Dispatch<SetStateAction<string>>;
  setCityLookupInteracted: Dispatch<SetStateAction<boolean>>;
  setCityQuery: Dispatch<SetStateAction<string>>;
  setStreetQuery: Dispatch<SetStateAction<string>>;
  setStreets: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupStreet[]>>;
  setActiveStreetIndex: Dispatch<SetStateAction<number>>;
  setWarehouseQuery: Dispatch<SetStateAction<string>>;
  setWarehouses: Dispatch<SetStateAction<WaybillAddressSuggestion[]>>;
  setActiveWarehouseIndex: Dispatch<SetStateAction<number>>;
}) {
  return useCallback((counterparty: BackofficeNovaPoshtaLookupCounterparty) => {
    const resolvedCounterpartyRef = (counterparty.counterparty_ref || counterparty.ref || "").trim();
    const fallbackContactRef = (counterparty.ref || "").trim();
    const normalizedName = (counterparty.label || counterparty.full_name || "").trim();
    const normalizedPhone = normalizeWaybillPhone(counterparty.phone || "");
    const normalizedCityRef = (counterparty.city_ref || "").trim();
    const normalizedCityLabel = (counterparty.city_label || "").trim();

    skipNextRecipientCounterpartyLookupRef.current = true;
    setRecipientCounterpartyQuery(normalizedName);
    setRecipientCounterpartyTypeLabel(resolveCounterpartyTypeDisplay(counterparty.counterparty_type));
    setRecipientCounterpartyTypeRaw(counterparty.counterparty_type || "");
    setRecipientCounterparties([]);
    setActiveRecipientCounterpartyIndex(-1);

    if (normalizedCityRef) {
      skipNextSettlementLookupRef.current = true;
      setSelectedSettlementRef("");
      setCityLookupInteracted(false);
      if (normalizedCityLabel) {
        setCityQuery(normalizedCityLabel);
      }
      setStreetQuery("");
      setStreets([]);
      setActiveStreetIndex(-1);
      setWarehouseQuery("");
      setWarehouses([]);
      setActiveWarehouseIndex(-1);
    }

    setPayload((prev) => {
      const nextPayload = {
        ...prev,
        recipient_counterparty_ref: resolvedCounterpartyRef,
        recipient_contact_ref: fallbackContactRef,
        recipient_name: normalizedName || prev.recipient_name,
        recipient_phone: normalizedPhone || prev.recipient_phone,
      };
      if (!normalizedCityRef) {
        return nextPayload;
      }
      return {
        ...nextPayload,
        recipient_city_ref: normalizedCityRef,
        recipient_city_label: normalizedCityLabel || prev.recipient_city_label,
        recipient_address_ref: "",
        recipient_address_label: "",
        recipient_street_ref: "",
        recipient_street_label: "",
        recipient_house: "",
        recipient_apartment: "",
      };
    });

    if (!token || !senderProfileId || !resolvedCounterpartyRef) {
      return;
    }
    const requestId = recipientCounterpartyDetailsRequestRef.current + 1;
    recipientCounterpartyDetailsRequestRef.current = requestId;
    void (async () => {
      try {
        const detailsResponse = await lookupBackofficeNovaPoshtaCounterpartyDetails(token, {
          sender_profile_id: senderProfileId,
          counterparty_ref: resolvedCounterpartyRef,
          counterparty_property: "Recipient",
          locale,
        });
        if (recipientCounterpartyDetailsRequestRef.current !== requestId) {
          return;
        }
        const details = detailsResponse.result;
        const detailsCityRef = (details.city_ref || "").trim();
        const detailsCityLabel = (details.city_label || "").trim();
        const detailsContactRef = (details.contact_ref || "").trim();
        const detailsContactName = (details.contact_name || "").trim();
        const detailsPhone = normalizeWaybillPhone(details.phone || "");
        if (detailsCityRef) {
          skipNextSettlementLookupRef.current = true;
          setSelectedSettlementRef("");
          setCityLookupInteracted(false);
          if (detailsCityLabel) {
            setCityQuery(detailsCityLabel);
          }
          setStreetQuery("");
          setStreets([]);
          setActiveStreetIndex(-1);
          setWarehouseQuery("");
          setWarehouses([]);
          setActiveWarehouseIndex(-1);
        }
        setPayload((prev) => {
          const nextPayload = {
            ...prev,
            recipient_counterparty_ref: resolvedCounterpartyRef || prev.recipient_counterparty_ref,
            recipient_contact_ref: detailsContactRef || prev.recipient_contact_ref,
            recipient_name: detailsContactName || prev.recipient_name,
            recipient_phone: detailsPhone || prev.recipient_phone,
          };
          if (!detailsCityRef) {
            return nextPayload;
          }
          return {
            ...nextPayload,
            recipient_city_ref: detailsCityRef,
            recipient_city_label: detailsCityLabel || prev.recipient_city_label,
            recipient_address_ref: "",
            recipient_address_label: "",
            recipient_street_ref: "",
            recipient_street_label: "",
            recipient_house: "",
            recipient_apartment: "",
          };
        });
      } catch {
        if (recipientCounterpartyDetailsRequestRef.current !== requestId) {
          return;
        }
      }
    })();
  }, [
    locale,
    recipientCounterpartyDetailsRequestRef,
    senderProfileId,
    setActiveRecipientCounterpartyIndex,
    setActiveStreetIndex,
    setActiveWarehouseIndex,
    setCityLookupInteracted,
    setCityQuery,
    setPayload,
    setRecipientCounterparties,
    setRecipientCounterpartyQuery,
    setRecipientCounterpartyTypeLabel,
    setRecipientCounterpartyTypeRaw,
    setSelectedSettlementRef,
    setStreetQuery,
    setStreets,
    setWarehouseQuery,
    setWarehouses,
    skipNextRecipientCounterpartyLookupRef,
    skipNextSettlementLookupRef,
    token,
  ]);
}
