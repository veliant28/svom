"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import {
  lookupBackofficeNovaPoshtaCounterpartyDetails,
  listBackofficeNovaPoshtaSenderProfiles,
  lookupBackofficeNovaPoshtaCounterparties,
  lookupBackofficeNovaPoshtaSettlements,
  lookupBackofficeNovaPoshtaStreets,
  lookupBackofficeNovaPoshtaWarehouses,
} from "@/features/backoffice/api/orders-api";
import { NovaPoshtaSendersEditorModal } from "@/features/backoffice/components/orders/nova-poshta-senders-editor-modal";
import { NovaPoshtaSendersLookupPanel } from "@/features/backoffice/components/orders/nova-poshta-senders-lookup-panel";
import { NovaPoshtaSendersList } from "@/features/backoffice/components/orders/nova-poshta-senders-list";
import { useNovaPoshtaSendersDropdownEffects } from "@/features/backoffice/components/orders/use-nova-poshta-senders-dropdown-effects";
import { useNovaPoshtaSendersLookupPanel } from "@/features/backoffice/components/orders/use-nova-poshta-senders-lookup-panel";
import { useNovaPoshtaSendersProfileActions } from "@/features/backoffice/components/orders/use-nova-poshta-senders-profile-actions";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import {
  EMPTY_SENDER_FORM,
  LETTER_QUERY_WAREHOUSE_LIMIT,
  getRawMetaString,
  isRefLike,
  type ModalAddressSuggestion,
} from "@/features/backoffice/components/orders/nova-poshta-senders.helpers";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
  BackofficeNovaPoshtaLookupWarehouse,
  BackofficeNovaPoshtaSenderProfile,
} from "@/features/backoffice/types/nova-poshta.types";

export function NovaPoshtaSendersPage() {
  const locale = useLocale();
  const t = useTranslations("backoffice.common");
  const { showApiError, showSuccess, showWarning } = useBackofficeFeedback();

  const [form, setForm] = useState({ ...EMPTY_SENDER_FORM });
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savingTokenOnly, setSavingTokenOnly] = useState(false);
  const [settingPrimaryId, setSettingPrimaryId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [lookupSenderId, setLookupSenderId] = useState("");
  const [settlementQuery, setSettlementQuery] = useState("");
  const [streetQuery, setStreetQuery] = useState("");
  const [warehouseQuery, setWarehouseQuery] = useState("");
  const [counterpartyQuery, setCounterpartyQuery] = useState("");
  const [counterpartyTypeDraft, setCounterpartyTypeDraft] = useState("");
  const [ownershipFormDraft, setOwnershipFormDraft] = useState("");
  const [edrpouDraft, setEdrpouDraft] = useState("");
  const [contactRefDraft, setContactRefDraft] = useState("");
  const [modalCityQuery, setModalCityQuery] = useState("");
  const [modalAddressQuery, setModalAddressQuery] = useState("");
  const [selectedSettlementRef, setSelectedSettlementRef] = useState("");
  const [lookupSettlementRef, setLookupSettlementRef] = useState("");
  const [lookupCityRef, setLookupCityRef] = useState("");
  const [counterparties, setCounterparties] = useState<BackofficeNovaPoshtaLookupCounterparty[]>([]);
  const [settlements, setSettlements] = useState<BackofficeNovaPoshtaLookupSettlement[]>([]);
  const [streets, setStreets] = useState<BackofficeNovaPoshtaLookupStreet[]>([]);
  const [warehouses, setWarehouses] = useState<BackofficeNovaPoshtaLookupWarehouse[]>([]);
  const [modalCities, setModalCities] = useState<BackofficeNovaPoshtaLookupSettlement[]>([]);
  const [modalAddresses, setModalAddresses] = useState<ModalAddressSuggestion[]>([]);
  const [counterpartyLoading, setCounterpartyLoading] = useState(false);
  const [counterpartyDetailsLoading, setCounterpartyDetailsLoading] = useState(false);
  const [modalCityLoading, setModalCityLoading] = useState(false);
  const [modalAddressLoading, setModalAddressLoading] = useState(false);
  const [settlementLoading, setSettlementLoading] = useState(false);
  const [streetLoading, setStreetLoading] = useState(false);
  const [warehouseLoading, setWarehouseLoading] = useState(false);
  const [activeCounterpartyIndex, setActiveCounterpartyIndex] = useState(-1);
  const [activeSettlementIndex, setActiveSettlementIndex] = useState(-1);
  const [activeStreetIndex, setActiveStreetIndex] = useState(-1);
  const [activeWarehouseIndex, setActiveWarehouseIndex] = useState(-1);
  const [activeModalCityIndex, setActiveModalCityIndex] = useState(-1);
  const [activeModalAddressIndex, setActiveModalAddressIndex] = useState(-1);
  const counterpartyRequestRef = useRef(0);
  const modalCityRequestRef = useRef(0);
  const modalAddressRequestRef = useRef(0);
  const skipNextCounterpartyLookupRef = useRef(false);
  const skipNextModalCityLookupRef = useRef(false);
  const skipNextModalAddressLookupRef = useRef(false);
  const counterpartyLookupRootRef = useRef<HTMLDivElement | null>(null);
  const settlementLookupRootRef = useRef<HTMLDivElement | null>(null);
  const streetLookupRootRef = useRef<HTMLDivElement | null>(null);
  const warehouseLookupRootRef = useRef<HTMLDivElement | null>(null);
  const modalCityLookupRootRef = useRef<HTMLDivElement | null>(null);
  const modalAddressLookupRootRef = useRef<HTMLDivElement | null>(null);
  const [selectedModalAddressRef, setSelectedModalAddressRef] = useState("");
  const [selectedModalAddressLabel, setSelectedModalAddressLabel] = useState("");

  const queryFn = useCallback((token: string) => listBackofficeNovaPoshtaSenderProfiles(token), []);
  const { token, data, isLoading, error, refetch } = useBackofficeQuery<BackofficeNovaPoshtaSenderProfile[]>(queryFn);

  const rows = useMemo(() => data ?? [], [data]);
  const defaultLookupSenderId = useMemo(() => rows.find((row) => row.is_default)?.id ?? rows[0]?.id ?? "", [rows]);
  const activeLookupSenderId = lookupSenderId || defaultLookupSenderId;
  const canLookup = Boolean(token && activeLookupSenderId);
  const lookupLocale = useMemo<"uk" | "ru" | "en">(() => {
    if (locale === "ru") {
      return "ru";
    }
    if (locale === "en") {
      return "en";
    }
    return "uk";
  }, [locale]);

  useEffect(() => {
    if (!rows.length) {
      if (lookupSenderId) {
        setLookupSenderId("");
      }
      return;
    }
    const selectedExists = rows.some((row) => row.id === lookupSenderId);
    if (selectedExists) {
      return;
    }
    const preferred = rows.find((row) => row.is_default) || rows[0];
    setLookupSenderId(preferred?.id ?? "");
  }, [lookupSenderId, rows]);

  useEffect(() => {
    setLookupSettlementRef("");
    setLookupCityRef("");
    setSettlements([]);
    setStreets([]);
    setWarehouses([]);
    setStreetQuery("");
    setWarehouseQuery("");
    setActiveSettlementIndex(-1);
    setActiveStreetIndex(-1);
    setActiveWarehouseIndex(-1);
  }, [lookupLocale, lookupSenderId]);

  const {
    applySettlementLookup,
    applyStreetLookup,
    applyWarehouseLookup,
  } = useNovaPoshtaSendersLookupPanel({
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
  });

  const fillFormFromSender = useCallback((item: BackofficeNovaPoshtaSenderProfile) => {
    const rawMeta = (item.raw_meta && typeof item.raw_meta === "object") ? item.raw_meta : {};
    const counterpartyLabel = getRawMetaString(rawMeta, "counterparty_label");
    const counterpartyType = getRawMetaString(rawMeta, "counterparty_type");
    const ownershipFormDescription = getRawMetaString(rawMeta, "ownership_form_description");
    const rawMetaEdrpou = getRawMetaString(rawMeta, "edrpou");
    const cityLabel = getRawMetaString(rawMeta, "city_label");
    const addressLabel = getRawMetaString(rawMeta, "address_label");
    const settlementRef = getRawMetaString(rawMeta, "settlement_ref");
    const normalizedCounterpartyLabel = counterpartyLabel && !isRefLike(counterpartyLabel)
      ? counterpartyLabel
      : (item.contact_name || "");
    const normalizedCityLabel = cityLabel && !isRefLike(cityLabel) ? cityLabel : "";
    const normalizedAddressLabel = addressLabel && !isRefLike(addressLabel) ? addressLabel : "";
    skipNextCounterpartyLookupRef.current = true;
    skipNextModalCityLookupRef.current = true;
    skipNextModalAddressLookupRef.current = true;
    setForm({
      api_token: "",
      counterparty_ref: item.counterparty_ref,
      address_ref: item.address_ref,
      city_ref: item.city_ref,
      phone: item.phone,
      contact_name: item.contact_name,
      is_active: item.is_active,
      is_default: item.is_default,
    });
    setContactRefDraft(item.contact_ref || "");
    setCounterpartyQuery(normalizedCounterpartyLabel);
    setCounterpartyTypeDraft(counterpartyType);
    setOwnershipFormDraft(ownershipFormDescription);
    setEdrpouDraft((item.edrpou || rawMetaEdrpou || "").trim());
    setModalCityQuery(normalizedCityLabel);
    setModalAddressQuery(normalizedAddressLabel);
    setSelectedSettlementRef(settlementRef);
    setCounterparties([]);
    setModalCities([]);
    setModalAddresses([]);
    setActiveCounterpartyIndex(-1);
    setActiveModalCityIndex(-1);
    setActiveModalAddressIndex(-1);
    setSelectedModalAddressRef("");
    setSelectedModalAddressLabel(normalizedAddressLabel);
  }, []);

  function openCreateSender() {
    setEditingId(null);
    setForm({ ...EMPTY_SENDER_FORM });
    setCounterpartyQuery("");
    setCounterpartyTypeDraft("");
    setOwnershipFormDraft("");
    setEdrpouDraft("");
    setContactRefDraft("");
    setModalCityQuery("");
    setModalAddressQuery("");
    setCounterparties([]);
    setModalCities([]);
    setModalAddresses([]);
    setActiveCounterpartyIndex(-1);
    setActiveModalCityIndex(-1);
    setActiveModalAddressIndex(-1);
    setSelectedModalAddressRef("");
    setSelectedModalAddressLabel("");
    setSelectedSettlementRef("");
    setIsEditorOpen(true);
  }

  function openEditSender(item: BackofficeNovaPoshtaSenderProfile) {
    setEditingId(item.id);
    fillFormFromSender(item);
    setIsEditorOpen(true);
  }

  function closeEditor() {
    setEditingId(null);
    setForm({ ...EMPTY_SENDER_FORM });
    setCounterpartyQuery("");
    setCounterpartyTypeDraft("");
    setOwnershipFormDraft("");
    setEdrpouDraft("");
    setContactRefDraft("");
    setModalCityQuery("");
    setModalAddressQuery("");
    setCounterparties([]);
    setModalCities([]);
    setModalAddresses([]);
    setActiveCounterpartyIndex(-1);
    setActiveModalCityIndex(-1);
    setActiveModalAddressIndex(-1);
    setSelectedModalAddressRef("");
    setSelectedModalAddressLabel("");
    setSelectedSettlementRef("");
    setIsEditorOpen(false);
  }

  const { submitForm, saveTokenOnly, setPrimarySender, deleteSender } = useNovaPoshtaSendersProfileActions({
    token,
    rows,
    form,
    editingId,
    saving,
    savingTokenOnly,
    settingPrimaryId,
    counterpartyQuery,
    counterpartyTypeDraft,
    ownershipFormDraft,
    edrpouDraft,
    contactRefDraft,
    modalCityQuery,
    modalAddressQuery,
    selectedSettlementRef,
    t,
    showApiError,
    showSuccess,
    showWarning,
    setForm,
    setEditingId,
    setSaving,
    setSavingTokenOnly,
    setSettingPrimaryId,
    setDeletingId,
    closeEditor,
    refetch,
  });

  const runCounterpartyLookup = useCallback(async (rawQuery: string) => {
    const query = rawQuery.trim();
    if (!token || !editingId || query.length < 2 || isRefLike(query)) {
      counterpartyRequestRef.current += 1;
      setCounterparties([]);
      setActiveCounterpartyIndex(-1);
      setCounterpartyLoading(false);
      return;
    }

    const requestId = counterpartyRequestRef.current + 1;
    counterpartyRequestRef.current = requestId;
    setCounterpartyLoading(true);
    try {
      const response = await lookupBackofficeNovaPoshtaCounterparties(token, {
        sender_profile_id: editingId,
        query,
        counterparty_property: "Sender",
        locale: lookupLocale,
      });
      if (counterpartyRequestRef.current !== requestId) {
        return;
      }
      setCounterparties(response.results);
      setActiveCounterpartyIndex(response.results.length > 0 ? 0 : -1);
    } catch (err: unknown) {
      if (counterpartyRequestRef.current !== requestId) {
        return;
      }
      void err;
      setCounterparties([]);
      setActiveCounterpartyIndex(-1);
    } finally {
      if (counterpartyRequestRef.current === requestId) {
        setCounterpartyLoading(false);
      }
    }
  }, [editingId, lookupLocale, token]);

  async function applyCounterparty(row: BackofficeNovaPoshtaLookupCounterparty) {
    const resolvedCounterpartyRef = row.ref || row.counterparty_ref || "";
    const resolvedDetailsRef = row.ref || row.counterparty_ref || "";
    skipNextCounterpartyLookupRef.current = true;
    setForm((prev) => ({
      ...prev,
      counterparty_ref: resolvedCounterpartyRef || prev.counterparty_ref,
      contact_name: row.full_name || prev.contact_name,
      city_ref: row.city_ref || prev.city_ref,
      phone: row.phone || prev.phone,
    }));
    setCounterpartyQuery(row.label || row.full_name || "");
    setCounterpartyTypeDraft((row.counterparty_type || "").trim());
    setOwnershipFormDraft((row.ownership_form_description || "").trim());
    setEdrpouDraft((row.edrpou || "").trim());
    if (row.city_label && !isRefLike(row.city_label)) {
      skipNextModalCityLookupRef.current = true;
      setModalCityQuery(row.city_label);
    }
    if (row.address && !isRefLike(row.address)) {
      skipNextModalAddressLookupRef.current = true;
      setModalAddressQuery(row.address);
    }
    setCounterparties([]);
    setActiveCounterpartyIndex(-1);

    if (!token || !editingId || !resolvedDetailsRef) {
      return;
    }

    setCounterpartyDetailsLoading(true);
    try {
      const detailsResponse = await lookupBackofficeNovaPoshtaCounterpartyDetails(token, {
        sender_profile_id: editingId,
        counterparty_ref: resolvedDetailsRef,
        counterparty_property: "Sender",
        locale: lookupLocale,
      });
      const details = detailsResponse.result;
      setForm((prev) => ({
        ...prev,
        phone: details.phone || prev.phone,
        city_ref: details.city_ref || prev.city_ref,
        address_ref: details.address_ref || prev.address_ref,
        contact_name: details.contact_name || prev.contact_name,
      }));
      if (details.contact_ref) {
        setContactRefDraft(details.contact_ref);
      }
      if (details.city_label && !isRefLike(details.city_label)) {
        skipNextModalCityLookupRef.current = true;
        setModalCityQuery(details.city_label);
      }
      if (details.address_label && !isRefLike(details.address_label)) {
        skipNextModalAddressLookupRef.current = true;
        setModalAddressQuery(details.address_label);
      }
    } catch (err: unknown) {
      showApiError(err, "Не удалось подтянуть данные контрагента.");
    } finally {
      setCounterpartyDetailsLoading(false);
    }
  }

  const runModalCityLookup = useCallback(async (rawQuery: string) => {
    const query = rawQuery.trim();
    if (!token || !editingId || query.length < 2 || isRefLike(query)) {
      modalCityRequestRef.current += 1;
      setModalCities([]);
      setActiveModalCityIndex(-1);
      setModalCityLoading(false);
      return;
    }

    const requestId = modalCityRequestRef.current + 1;
    modalCityRequestRef.current = requestId;
    setModalCityLoading(true);
    try {
      const response = await lookupBackofficeNovaPoshtaSettlements(token, {
        sender_profile_id: editingId,
        query,
        locale: lookupLocale,
      });
      if (modalCityRequestRef.current !== requestId) {
        return;
      }
      setModalCities(response.results);
      setActiveModalCityIndex(response.results.length > 0 ? 0 : -1);
    } catch (err: unknown) {
      if (modalCityRequestRef.current !== requestId) {
        return;
      }
      void err;
      setModalCities([]);
      setActiveModalCityIndex(-1);
    } finally {
      if (modalCityRequestRef.current === requestId) {
        setModalCityLoading(false);
      }
    }
  }, [editingId, lookupLocale, token]);

  function applyModalCity(item: BackofficeNovaPoshtaLookupSettlement) {
    skipNextModalCityLookupRef.current = true;
    skipNextModalAddressLookupRef.current = true;
    const resolvedCityRef = item.delivery_city_ref || item.ref || "";
    const resolvedSettlementRef = item.settlement_ref || item.ref || "";
    setForm((prev) => ({
      ...prev,
      city_ref: resolvedCityRef || prev.city_ref,
    }));
    setSelectedSettlementRef(resolvedSettlementRef);
    setModalCityQuery(item.label || item.main_description || resolvedCityRef);
    setModalCities([]);
    setActiveModalCityIndex(-1);
    setModalAddresses([]);
    setActiveModalAddressIndex(-1);
    setModalAddressQuery("");
    setSelectedModalAddressRef("");
    setSelectedModalAddressLabel("");
    setForm((prev) => ({ ...prev, address_ref: "" }));
  }

  const runModalAddressLookup = useCallback(async (rawQuery: string) => {
    const query = rawQuery.trim();
    const lookupQuery = query.split(",")[0]?.trim() ?? "";
    const rawCityRef = form.city_ref.trim();
    const cityRef = /^[0-9a-fA-F-]{36}$/.test(rawCityRef) ? rawCityRef : "";
    const isDigitsOnlyQuery = /^\d+$/.test(lookupQuery);
    const minQueryLength = isDigitsOnlyQuery ? 1 : 2;
    if (!token || !editingId || lookupQuery.length < minQueryLength || isRefLike(lookupQuery)) {
      modalAddressRequestRef.current += 1;
      setModalAddresses([]);
      setActiveModalAddressIndex(-1);
      setModalAddressLoading(false);
      return;
    }

    const requestId = modalAddressRequestRef.current + 1;
    modalAddressRequestRef.current = requestId;
    setModalAddressLoading(true);
    try {
      const hasLetters = /[A-Za-zА-Яа-яІіЇїЄєҐґ]/.test(lookupQuery);
      const shouldSearchWarehouses = true;
      const shouldSearchStreets = hasLetters && Boolean(selectedSettlementRef.trim());

      const [warehousesResponse, streetsResponse] = await Promise.all([
        shouldSearchWarehouses
          ? lookupBackofficeNovaPoshtaWarehouses(token, {
            sender_profile_id: editingId,
            city_ref: cityRef,
            query: lookupQuery,
            locale: lookupLocale,
          })
          : Promise.resolve({ results: [] as BackofficeNovaPoshtaLookupWarehouse[] }),
        shouldSearchStreets
          ? lookupBackofficeNovaPoshtaStreets(token, {
            sender_profile_id: editingId,
            settlement_ref: selectedSettlementRef,
            query: lookupQuery,
            locale: lookupLocale,
          })
          : Promise.resolve({ results: [] as BackofficeNovaPoshtaLookupStreet[] }),
      ]);
      if (modalAddressRequestRef.current !== requestId) {
        return;
      }

      const warehouseRows: ModalAddressSuggestion[] = warehousesResponse.results.map((item) => {
        const normalizedNumber = String(item.number || "").trim();
        const normalizedDescription = String(item.description || item.full_description || "").trim();
        const descriptionPrefix = normalizedDescription.includes(":")
          ? normalizedDescription.split(":")[0].trim()
          : normalizedDescription;
        const descriptionTail = normalizedDescription.includes(":")
          ? normalizedDescription.split(":").slice(1).join(":").trim()
          : "";
        const shortWithoutCity = String(item.label || "").split(",").slice(1).join(",").trim();
        const fallbackStreet = shortWithoutCity || descriptionTail || item.ref;
        const normalizedCategory = String(item.category || "").toLowerCase();
        const normalizedType = String(item.type || "").toLowerCase();
        const normalizedText = `${normalizedDescription} ${shortWithoutCity}`.toLowerCase();
        const isPostomat =
          normalizedCategory.includes("postomat")
          || normalizedType.includes("postomat")
          || normalizedType.includes("поштомат")
          || normalizedType.includes("постомат")
          || normalizedText.includes("поштомат")
          || normalizedText.includes("постомат");
        const typeLabel = isPostomat ? "Поштомат" : "Відділення";
        const fallbackLabel = normalizedNumber ? `${typeLabel} №${normalizedNumber}` : typeLabel;
        const label = descriptionPrefix || fallbackLabel;
        const subtitle = fallbackStreet;
        return {
          kind: "warehouse",
          ref: item.ref,
          label,
          subtitle,
        };
      });
      const streetRows: ModalAddressSuggestion[] = streetsResponse.results.map((item) => ({
        kind: "street",
        ref: item.street_ref,
        label: item.label || item.street_name || item.street_ref,
        subtitle: "",
      }));
      const limitedWarehouseRows = hasLetters
        ? warehouseRows.slice(0, LETTER_QUERY_WAREHOUSE_LIMIT)
        : warehouseRows;
      const merged = hasLetters ? [...streetRows, ...limitedWarehouseRows] : [...warehouseRows, ...streetRows];
      setModalAddresses(merged);
      setActiveModalAddressIndex(merged.length > 0 ? 0 : -1);
    } catch (err: unknown) {
      if (modalAddressRequestRef.current !== requestId) {
        return;
      }
      void err;
      setModalAddresses([]);
      setActiveModalAddressIndex(-1);
    } finally {
      if (modalAddressRequestRef.current === requestId) {
        setModalAddressLoading(false);
      }
    }
  }, [editingId, form.city_ref, lookupLocale, selectedSettlementRef, token]);

  function applyModalAddress(item: ModalAddressSuggestion) {
    const suffix = modalAddressQuery.split(",").slice(1).join(",").trim();
    const nextQuery = item.kind === "street" && suffix ? `${item.label}, ${suffix}` : item.label;
    skipNextModalAddressLookupRef.current = true;
    setForm((prev) => ({
      ...prev,
      address_ref: item.ref || prev.address_ref,
    }));
    setSelectedModalAddressRef(item.ref);
    setSelectedModalAddressLabel(item.label);
    setModalAddressQuery(nextQuery);
    setModalAddresses([]);
    setActiveModalAddressIndex(-1);
  }

  useNovaPoshtaSendersDropdownEffects({
    isEditorOpen,
    counterpartyQuery,
    modalCityQuery,
    modalAddressQuery,
    counterparties,
    modalCities,
    modalAddresses,
    settlements,
    streets,
    warehouses,
    activeCounterpartyIndex,
    activeModalCityIndex,
    activeModalAddressIndex,
    activeSettlementIndex,
    activeStreetIndex,
    activeWarehouseIndex,
    counterpartyLookupRootRef,
    modalCityLookupRootRef,
    modalAddressLookupRootRef,
    settlementLookupRootRef,
    streetLookupRootRef,
    warehouseLookupRootRef,
    skipNextCounterpartyLookupRef,
    skipNextModalCityLookupRef,
    skipNextModalAddressLookupRef,
    runCounterpartyLookup,
    runModalCityLookup,
    runModalAddressLookup,
    setCounterparties,
    setModalCities,
    setModalAddresses,
    setSettlements,
    setStreets,
    setWarehouses,
    setActiveCounterpartyIndex,
    setActiveModalCityIndex,
    setActiveModalAddressIndex,
    setActiveSettlementIndex,
    setActiveStreetIndex,
    setActiveWarehouseIndex,
  });

  return (
    <section>
      <PageHeader
        title={t("orders.modals.waybill.settings.title")}
        description={t("orders.modals.waybill.settings.subtitle")}
      />

      <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
        <NovaPoshtaSendersList
          rows={rows}
          isLoading={isLoading}
          error={error}
          settingPrimaryId={settingPrimaryId}
          deletingId={deletingId}
          t={t}
          onCreate={openCreateSender}
          onEdit={openEditSender}
          onSetPrimary={(senderId) => { void setPrimarySender(senderId); }}
          onDelete={(item) => { void deleteSender(item); }}
        />

        <NovaPoshtaSendersLookupPanel
          canLookup={canLookup}
          lookupSettlementRef={lookupSettlementRef}
          lookupCityRef={lookupCityRef}
          settlementLookupRootRef={settlementLookupRootRef}
          streetLookupRootRef={streetLookupRootRef}
          warehouseLookupRootRef={warehouseLookupRootRef}
          settlementQuery={settlementQuery}
          streetQuery={streetQuery}
          warehouseQuery={warehouseQuery}
          settlements={settlements}
          streets={streets}
          warehouses={warehouses}
          settlementLoading={settlementLoading}
          streetLoading={streetLoading}
          warehouseLoading={warehouseLoading}
          activeSettlementIndex={activeSettlementIndex}
          activeStreetIndex={activeStreetIndex}
          activeWarehouseIndex={activeWarehouseIndex}
          t={t}
          onSettlementQueryChange={(next) => {
            setSettlementQuery(next);
            setLookupSettlementRef("");
            setLookupCityRef("");
            setStreetQuery("");
            setWarehouseQuery("");
            setStreets([]);
            setWarehouses([]);
            setActiveStreetIndex(-1);
            setActiveWarehouseIndex(-1);
          }}
          onStreetQueryChange={setStreetQuery}
          onWarehouseQueryChange={setWarehouseQuery}
          setSettlements={setSettlements}
          setStreets={setStreets}
          setWarehouses={setWarehouses}
          setActiveSettlementIndex={setActiveSettlementIndex}
          setActiveStreetIndex={setActiveStreetIndex}
          setActiveWarehouseIndex={setActiveWarehouseIndex}
          onSettlementSelect={applySettlementLookup}
          onStreetSelect={applyStreetLookup}
          onWarehouseSelect={applyWarehouseLookup}
        />
      </div>

      {isEditorOpen ? (
        <NovaPoshtaSendersEditorModal
          editingId={editingId}
          rows={rows}
          form={form}
          saving={saving}
          savingTokenOnly={savingTokenOnly}
          counterpartyLookupRootRef={counterpartyLookupRootRef}
          modalCityLookupRootRef={modalCityLookupRootRef}
          modalAddressLookupRootRef={modalAddressLookupRootRef}
          counterpartyQuery={counterpartyQuery}
          counterparties={counterparties}
          counterpartyLoading={counterpartyLoading}
          counterpartyDetailsLoading={counterpartyDetailsLoading}
          activeCounterpartyIndex={activeCounterpartyIndex}
          modalCityQuery={modalCityQuery}
          modalCities={modalCities}
          modalCityLoading={modalCityLoading}
          activeModalCityIndex={activeModalCityIndex}
          modalAddressQuery={modalAddressQuery}
          modalAddresses={modalAddresses}
          modalAddressLoading={modalAddressLoading}
          activeModalAddressIndex={activeModalAddressIndex}
          selectedModalAddressRef={selectedModalAddressRef}
          selectedModalAddressLabel={selectedModalAddressLabel}
          t={t}
          setForm={setForm}
          setCounterpartyQuery={setCounterpartyQuery}
          setCounterparties={setCounterparties}
          setActiveCounterpartyIndex={setActiveCounterpartyIndex}
          setModalCityQuery={setModalCityQuery}
          setModalCities={setModalCities}
          setActiveModalCityIndex={setActiveModalCityIndex}
          setSelectedSettlementRef={setSelectedSettlementRef}
          setModalAddressQuery={setModalAddressQuery}
          setModalAddresses={setModalAddresses}
          setActiveModalAddressIndex={setActiveModalAddressIndex}
          setSelectedModalAddressRef={setSelectedModalAddressRef}
          setSelectedModalAddressLabel={setSelectedModalAddressLabel}
          onClose={closeEditor}
          onSubmit={() => { void submitForm(); }}
          onSaveTokenOnly={() => { void saveTokenOnly(); }}
          onCounterpartySelect={(row) => { void applyCounterparty(row); }}
          onModalCitySelect={applyModalCity}
          onModalAddressSelect={applyModalAddress}
        />
      ) : null}
    </section>
  );
}
