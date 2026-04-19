"use client";

import {
  Building2,
  CheckCircle2,
  KeyRound,
  MapPin,
  Pencil,
  Plus,
  Star,
  TriangleAlert,
  Trash2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import {
  createBackofficeNovaPoshtaSenderProfile,
  deleteBackofficeNovaPoshtaSenderProfile,
  lookupBackofficeNovaPoshtaCounterpartyDetails,
  listBackofficeNovaPoshtaSenderProfiles,
  lookupBackofficeNovaPoshtaCounterparties,
  lookupBackofficeNovaPoshtaSettlements,
  lookupBackofficeNovaPoshtaStreets,
  lookupBackofficeNovaPoshtaWarehouses,
  updateBackofficeNovaPoshtaSenderProfile,
} from "@/features/backoffice/api/orders-api";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
  BackofficeNovaPoshtaLookupWarehouse,
  BackofficeNovaPoshtaSenderProfile,
} from "@/features/backoffice/types/nova-poshta.types";

type ModalAddressSuggestion = {
  kind: "warehouse" | "street";
  ref: string;
  label: string;
  subtitle: string;
};

const LETTER_QUERY_WAREHOUSE_LIMIT = 8;
const DRAFT_SENDER_NAME = "Черновик отправителя";
type SenderTypeValue = "private_person" | "fop" | "business";

const EMPTY_FORM = {
  api_token: "",
  counterparty_ref: "",
  address_ref: "",
  city_ref: "",
  phone: "",
  contact_name: "",
  is_active: true,
  is_default: false,
};

function normalizeSenderTypeHint(value: string | null | undefined): SenderTypeValue | "unknown" {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "unknown";
  }
  const compact = normalized.replace(/[\s_-]+/g, "");
  if (normalized.includes("фоп") || normalized.includes("флп") || compact.includes("fop")) {
    return "fop";
  }
  if (
    normalized.includes("organization")
    || normalized.includes("company")
    || compact.includes("business")
    || compact.includes("legalentity")
  ) {
    return "business";
  }
  if (
    normalized === "private_person"
    || compact.includes("privateperson")
    || compact.includes("privatperson")
    || compact.includes("physicalperson")
  ) {
    return "private_person";
  }
  return "unknown";
}

function resolveSenderTypeFromHints(...values: Array<string | null | undefined>): SenderTypeValue {
  let hasPrivatePerson = false;
  for (const value of values) {
    const normalized = normalizeSenderTypeHint(value);
    if (normalized === "fop" || normalized === "business") {
      return normalized;
    }
    if (normalized === "private_person") {
      hasPrivatePerson = true;
    }
  }
  return hasPrivatePerson ? "private_person" : "private_person";
}

function isUuidLike(value: string): boolean {
  return /^[0-9A-Za-z]{8}-[0-9A-Za-z]{4}-[0-9A-Za-z]{4}-[0-9A-Za-z]{4}-[0-9A-Za-z]{12}$/.test(value.trim());
}

function isPendingRefLike(value: string): boolean {
  return /^pending-[\w-]+$/i.test(value.trim());
}

function isRefLike(value: string): boolean {
  const normalized = value.trim();
  return isUuidLike(normalized) || isPendingRefLike(normalized);
}

function getRawMetaString(meta: Record<string, unknown> | null | undefined, key: string): string {
  if (!meta || typeof meta !== "object") {
    return "";
  }
  const value = meta[key];
  return typeof value === "string" ? value.trim() : "";
}

function formatWarehouseLookupDisplay(item: BackofficeNovaPoshtaLookupWarehouse): { label: string; subtitle: string } {
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
  return {
    label: descriptionPrefix || fallbackLabel,
    subtitle: fallbackStreet,
  };
}

function scrollDropdownOptionIntoView(
  root: HTMLDivElement | null,
  scope: string,
  index: number,
) {
  if (!root || index < 0) {
    return;
  }
  const option = root.querySelector<HTMLElement>(`[data-nav-scope="${scope}"][data-nav-index="${index}"]`);
  option?.scrollIntoView({ block: "nearest" });
}

export function NovaPoshtaSendersPage() {
  const locale = useLocale();
  const t = useTranslations("backoffice.common");
  const { showApiError, showSuccess, showWarning } = useBackofficeFeedback();

  const [form, setForm] = useState({ ...EMPTY_FORM });
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
  const settlementRequestRef = useRef(0);
  const streetRequestRef = useRef(0);
  const warehouseRequestRef = useRef(0);
  const counterpartyRequestRef = useRef(0);
  const modalCityRequestRef = useRef(0);
  const modalAddressRequestRef = useRef(0);
  const skipNextSettlementLookupRef = useRef(false);
  const skipNextStreetLookupRef = useRef(false);
  const skipNextWarehouseLookupRef = useRef(false);
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

  const rows = data ?? [];
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
    setForm({ ...EMPTY_FORM });
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
    setForm({ ...EMPTY_FORM });
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

  async function enforceSingleDefaultSender(preferredDefaultId: string) {
    if (!token) {
      return;
    }
    const profiles = await listBackofficeNovaPoshtaSenderProfiles(token);
    const defaults = profiles.filter((profile) => profile.is_default);
    if (defaults.length <= 1) {
      return;
    }

    const keepId = defaults.some((profile) => profile.id === preferredDefaultId)
      ? preferredDefaultId
      : defaults[0].id;

    await Promise.all(
      defaults
        .filter((profile) => profile.id !== keepId)
        .map((profile) => updateBackofficeNovaPoshtaSenderProfile(token, profile.id, { is_default: false })),
    );
  }

  async function submitForm() {
    if (!token || saving) {
      return;
    }
    setSaving(true);
    try {
      const editingSender = editingId ? rows.find((row) => row.id === editingId) : null;
      const hasStoredToken = Boolean((editingSender?.api_token_masked || "").trim());
      if (!editingId && !form.api_token.trim()) {
        showWarning("Сначала сохраните API токен отправителя.");
        return;
      }
      if (editingId && !hasStoredToken && !form.api_token.trim()) {
        showWarning("Сначала сохраните API токен отправителя.");
        return;
      }
      const normalizedCounterpartyRef = form.counterparty_ref.trim();
      const normalizedContactRef = contactRefDraft.trim() || (editingSender?.contact_ref || "").trim() || normalizedCounterpartyRef;
      const normalizedAddressRef = form.address_ref.trim();
      const normalizedCityRef = form.city_ref.trim();
      const normalizedPhone = form.phone.trim();
      const normalizedContactName = form.contact_name.trim();
      if (!isUuidLike(normalizedCounterpartyRef)) {
        showWarning("Выберите контрагента из списка.");
        return;
      }
      if (!isUuidLike(normalizedContactRef)) {
        showWarning("Выберите контрагента из списка, чтобы подтянулся корректный контакт.");
        return;
      }
      if (!isUuidLike(normalizedCityRef)) {
        showWarning("Выберите город из списка.");
        return;
      }
      if (!isUuidLike(normalizedAddressRef)) {
        showWarning("Выберите отделение/почтомат/адрес из списка.");
        return;
      }
      const existingName = (editingSender?.name || "").trim();
      const normalizedName = (existingName && existingName !== DRAFT_SENDER_NAME)
        ? existingName
        : (normalizedContactName || normalizedPhone || normalizedCounterpartyRef || DRAFT_SENDER_NAME);
      const existingRawMeta = (editingSender?.raw_meta && typeof editingSender.raw_meta === "object")
        ? editingSender.raw_meta
        : {};
      const nextRawMeta: Record<string, unknown> = { ...existingRawMeta };
      const normalizedCounterpartyLabel = counterpartyQuery.trim();
      const normalizedCounterpartyType = counterpartyTypeDraft.trim();
      const normalizedOwnershipForm = ownershipFormDraft.trim();
      const normalizedCityLabel = modalCityQuery.trim();
      const normalizedAddressLabel = modalAddressQuery.trim();
      const normalizedSettlementRef = selectedSettlementRef.trim();
      const normalizedEdrpou = (edrpouDraft || editingSender?.edrpou || "").trim();
      const resolvedSenderType = resolveSenderTypeFromHints(
        editingSender?.sender_type,
        getRawMetaString(existingRawMeta, "inferred_sender_type"),
        normalizedCounterpartyType,
        normalizedOwnershipForm,
        normalizedCounterpartyLabel,
        normalizedContactName,
        normalizedName,
      );
      if (normalizedCounterpartyLabel && !isRefLike(normalizedCounterpartyLabel)) {
        nextRawMeta.counterparty_label = normalizedCounterpartyLabel;
      } else {
        delete nextRawMeta.counterparty_label;
      }
      if (normalizedCounterpartyType) {
        nextRawMeta.counterparty_type = normalizedCounterpartyType;
      } else {
        delete nextRawMeta.counterparty_type;
      }
      if (normalizedOwnershipForm) {
        nextRawMeta.ownership_form_description = normalizedOwnershipForm;
      } else {
        delete nextRawMeta.ownership_form_description;
      }
      if (normalizedEdrpou) {
        nextRawMeta.edrpou = normalizedEdrpou;
      } else {
        delete nextRawMeta.edrpou;
      }
      nextRawMeta.inferred_sender_type = resolvedSenderType;
      if (normalizedCityLabel && !isRefLike(normalizedCityLabel)) {
        nextRawMeta.city_label = normalizedCityLabel;
      } else {
        delete nextRawMeta.city_label;
      }
      if (normalizedAddressLabel && !isRefLike(normalizedAddressLabel)) {
        nextRawMeta.address_label = normalizedAddressLabel;
      } else {
        delete nextRawMeta.address_label;
      }
      if (normalizedSettlementRef) {
        nextRawMeta.settlement_ref = normalizedSettlementRef;
      } else {
        delete nextRawMeta.settlement_ref;
      }

      const payloadBase: Record<string, unknown> = {
        ...form,
        name: normalizedName,
        sender_type: resolvedSenderType,
        counterparty_ref: normalizedCounterpartyRef,
        contact_ref: normalizedContactRef,
        address_ref: normalizedAddressRef,
        city_ref: normalizedCityRef,
        phone: normalizedPhone,
        contact_name: normalizedContactName,
        edrpou: normalizedEdrpou,
        raw_meta: nextRawMeta,
      };

      let savedProfile: BackofficeNovaPoshtaSenderProfile;
      if (editingId) {
        const updatePayload: Record<string, unknown> = { ...payloadBase };
        if (!form.api_token.trim()) {
          delete updatePayload.api_token;
        }
        savedProfile = await updateBackofficeNovaPoshtaSenderProfile(token, editingId, updatePayload);
        showSuccess(t("orders.messages.senderUpdated"));
      } else {
        savedProfile = await createBackofficeNovaPoshtaSenderProfile(token, payloadBase as {
          name: string;
          sender_type: "private_person" | "fop" | "business";
          api_token: string;
          counterparty_ref: string;
          contact_ref: string;
          address_ref: string;
          city_ref: string;
          phone: string;
          contact_name?: string;
          edrpou?: string;
          is_active: boolean;
          is_default: boolean;
          raw_meta?: Record<string, unknown>;
        });
        showSuccess(t("orders.messages.senderCreated"));
      }
      if (savedProfile.is_default) {
        await enforceSingleDefaultSender(savedProfile.id);
      }
      closeEditor();
      await refetch();
    } catch (err: unknown) {
      showApiError(err, t("orders.messages.senderSaveFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function saveTokenOnly() {
    if (!token || savingTokenOnly) {
      return;
    }
    const nextToken = form.api_token.trim();
    if (!nextToken) {
      showWarning("Введите API токен.");
      return;
    }
    setSavingTokenOnly(true);
    try {
      if (editingId) {
        await updateBackofficeNovaPoshtaSenderProfile(token, editingId, { api_token: nextToken });
        showSuccess(t("orders.messages.senderUpdated"));
      } else {
        const pendingSuffix = `${Date.now()}`.slice(-6);
        const created = await createBackofficeNovaPoshtaSenderProfile(token, {
          name: form.contact_name.trim() || form.phone.trim() || DRAFT_SENDER_NAME,
          sender_type: "private_person",
          api_token: nextToken,
          counterparty_ref: form.counterparty_ref.trim() || `pending-counterparty-${pendingSuffix}`,
          contact_ref: form.counterparty_ref.trim() || `pending-contact-${pendingSuffix}`,
          address_ref: form.address_ref.trim() || `pending-address-${pendingSuffix}`,
          city_ref: form.city_ref.trim() || `pending-city-${pendingSuffix}`,
          phone: form.phone.trim() || "+380000000000",
          contact_name: form.contact_name.trim(),
          is_active: true,
          is_default: false,
        });
        setEditingId(created.id);
        showSuccess("Токен сохранен. Теперь заполните отправителя и сохраните профиль.");
      }
      setForm((prev) => ({ ...prev, api_token: "" }));
      await refetch();
    } catch (err: unknown) {
      showApiError(err, t("orders.messages.senderSaveFailed"));
    } finally {
      setSavingTokenOnly(false);
    }
  }

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
      const hasDigits = /\d/.test(lookupQuery);
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

  useEffect(() => {
    if (!isEditorOpen) {
      return;
    }

    if (skipNextCounterpartyLookupRef.current) {
      skipNextCounterpartyLookupRef.current = false;
      return;
    }

    const timerId = window.setTimeout(() => {
      void runCounterpartyLookup(counterpartyQuery);
    }, 280);

    return () => {
      window.clearTimeout(timerId);
    };
  }, [counterpartyQuery, isEditorOpen, runCounterpartyLookup]);

  useEffect(() => {
    if (!isEditorOpen) {
      return;
    }
    if (skipNextModalCityLookupRef.current) {
      skipNextModalCityLookupRef.current = false;
      return;
    }
    const timerId = window.setTimeout(() => {
      void runModalCityLookup(modalCityQuery);
    }, 280);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [isEditorOpen, modalCityQuery, runModalCityLookup]);

  useEffect(() => {
    if (!isEditorOpen) {
      return;
    }
    if (skipNextModalAddressLookupRef.current) {
      skipNextModalAddressLookupRef.current = false;
      return;
    }
    const timerId = window.setTimeout(() => {
      void runModalAddressLookup(modalAddressQuery);
    }, 280);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [isEditorOpen, modalAddressQuery, runModalAddressLookup]);

  useEffect(() => {
    if (!isEditorOpen || (!counterparties.length && !modalCities.length && !modalAddresses.length)) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!counterpartyLookupRootRef.current?.contains(target)) {
        setCounterparties([]);
        setActiveCounterpartyIndex(-1);
      }
      if (!modalCityLookupRootRef.current?.contains(target)) {
        setModalCities([]);
        setActiveModalCityIndex(-1);
      }
      if (!modalAddressLookupRootRef.current?.contains(target)) {
        setModalAddresses([]);
        setActiveModalAddressIndex(-1);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [counterparties.length, isEditorOpen, modalAddresses.length, modalCities.length]);

  useEffect(() => {
    if (!settlements.length && !streets.length && !warehouses.length) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!settlementLookupRootRef.current?.contains(target)) {
        setSettlements([]);
        setActiveSettlementIndex(-1);
      }
      if (!streetLookupRootRef.current?.contains(target)) {
        setStreets([]);
        setActiveStreetIndex(-1);
      }
      if (!warehouseLookupRootRef.current?.contains(target)) {
        setWarehouses([]);
        setActiveWarehouseIndex(-1);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [settlements.length, streets.length, warehouses.length]);

  useEffect(() => {
    if (!counterparties.length || activeCounterpartyIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(counterpartyLookupRootRef.current, "counterparty", activeCounterpartyIndex);
  }, [activeCounterpartyIndex, counterparties.length]);

  useEffect(() => {
    if (!modalCities.length || activeModalCityIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(modalCityLookupRootRef.current, "modal-city", activeModalCityIndex);
  }, [activeModalCityIndex, modalCities.length]);

  useEffect(() => {
    if (!modalAddresses.length || activeModalAddressIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(modalAddressLookupRootRef.current, "modal-address", activeModalAddressIndex);
  }, [activeModalAddressIndex, modalAddresses.length]);

  useEffect(() => {
    if (!settlements.length || activeSettlementIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(settlementLookupRootRef.current, "lookup-settlement", activeSettlementIndex);
  }, [activeSettlementIndex, settlements.length]);

  useEffect(() => {
    if (!streets.length || activeStreetIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(streetLookupRootRef.current, "lookup-street", activeStreetIndex);
  }, [activeStreetIndex, streets.length]);

  useEffect(() => {
    if (!warehouses.length || activeWarehouseIndex < 0) {
      return;
    }
    scrollDropdownOptionIntoView(warehouseLookupRootRef.current, "lookup-warehouse", activeWarehouseIndex);
  }, [activeWarehouseIndex, warehouses.length]);

  async function setPrimarySender(senderId: string) {
    if (!token || settingPrimaryId === senderId) {
      return;
    }
    setSettingPrimaryId(senderId);
    try {
      const savedProfile = await updateBackofficeNovaPoshtaSenderProfile(token, senderId, { is_default: true });
      if (savedProfile.is_default) {
        await enforceSingleDefaultSender(savedProfile.id);
      }
      showSuccess(t("orders.messages.senderUpdated"));
      await refetch();
    } catch (err: unknown) {
      showApiError(err, t("orders.messages.senderSaveFailed"));
    } finally {
      setSettingPrimaryId(null);
    }
  }

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
    } catch (err: unknown) {
      if (settlementRequestRef.current !== requestId) {
        return;
      }
      void err;
      setSettlements([]);
      setActiveSettlementIndex(-1);
    } finally {
      if (settlementRequestRef.current === requestId) {
        setSettlementLoading(false);
      }
    }
  }, [activeLookupSenderId, lookupLocale, token]);

  function applySettlementLookup(item: BackofficeNovaPoshtaLookupSettlement) {
    skipNextSettlementLookupRef.current = true;
    setLookupSettlementRef(item.settlement_ref || item.ref || "");
    setLookupCityRef(item.delivery_city_ref || item.ref || "");
    setSettlementQuery(item.label || item.main_description || "");
    setSettlements([]);
    setActiveSettlementIndex(-1);
    setStreetQuery("");
    setWarehouseQuery("");
    setStreets([]);
    setWarehouses([]);
    setActiveStreetIndex(-1);
    setActiveWarehouseIndex(-1);
  }

  const runStreetLookup = useCallback(async (rawQuery: string) => {
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
    } catch (err: unknown) {
      if (streetRequestRef.current !== requestId) {
        return;
      }
      void err;
      setStreets([]);
      setActiveStreetIndex(-1);
    } finally {
      if (streetRequestRef.current === requestId) {
        setStreetLoading(false);
      }
    }
  }, [activeLookupSenderId, lookupLocale, lookupSettlementRef, token]);

  function applyStreetLookup(item: BackofficeNovaPoshtaLookupStreet) {
    skipNextStreetLookupRef.current = true;
    setStreetQuery(item.label || item.street_name || "");
    setStreets([]);
    setActiveStreetIndex(-1);
  }

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
    } catch (err: unknown) {
      if (warehouseRequestRef.current !== requestId) {
        return;
      }
      void err;
      setWarehouses([]);
      setActiveWarehouseIndex(-1);
    } finally {
      if (warehouseRequestRef.current === requestId) {
        setWarehouseLoading(false);
      }
    }
  }, [activeLookupSenderId, lookupCityRef, lookupLocale, token]);

  function applyWarehouseLookup(item: BackofficeNovaPoshtaLookupWarehouse) {
    const formatted = formatWarehouseLookupDisplay(item);
    skipNextWarehouseLookupRef.current = true;
    setWarehouseQuery(formatted.label);
    setWarehouses([]);
    setActiveWarehouseIndex(-1);
  }

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
      void runStreetLookup(streetQuery);
    }, 280);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [runStreetLookup, streetQuery]);

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

  return (
    <section>
      <PageHeader
        title={t("orders.modals.waybill.settings.title")}
        description={t("orders.modals.waybill.settings.subtitle")}
      />

      <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
        <div>
          <div className="mb-4 rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
            <div className="mb-3 flex items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold">{t("orders.modals.waybill.settings.title")}</h3>
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {t("orders.modals.waybill.settings.subtitle")}
                </p>
              </div>
              <button
                type="button"
                className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                onClick={openCreateSender}
              >
                <Plus className="h-4 w-4" />
                {t("orders.modals.waybill.settings.actions.create")}
              </button>
            </div>

            <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("orders.modals.waybill.settings.empty")}>
              <div className="grid gap-2">
                {rows.map((item) => {
                  const rawMeta = (item.raw_meta && typeof item.raw_meta === "object") ? item.raw_meta : {};
                  const counterpartyLabel = getRawMetaString(rawMeta, "counterparty_label");
                  const cityLabel = getRawMetaString(rawMeta, "city_label");
                  const addressLabel = getRawMetaString(rawMeta, "address_label");
                  const counterpartyDisplay = counterpartyLabel || "Не выбран";
                  const cityDisplay = cityLabel || "Не выбран";
                  const addressDisplay = addressLabel || "Не выбран";
                  return (
                  <article key={item.id} className="rounded-lg border p-2.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold">{item.contact_name || item.phone || item.counterparty_ref}</p>
                        <p className="text-xs" style={{ color: "var(--muted)" }}>{item.phone || "-"}</p>
                      </div>
                      <div className="flex flex-wrap items-center justify-end gap-1.5">
                        {item.is_default ? (
                          <BackofficeStatusChip tone="blue" icon={Star}>
                            {t("orders.modals.waybill.settings.default")}
                          </BackofficeStatusChip>
                        ) : null}
                        <BackofficeStatusChip
                          tone={item.is_active ? "success" : "gray"}
                          icon={item.is_active ? CheckCircle2 : TriangleAlert}
                        >
                          {item.is_active ? "Активен" : "Неактивен"}
                        </BackofficeStatusChip>
                      </div>
                    </div>

                    <div className="mt-2 flex items-end justify-between gap-2">
                      <div className="min-w-0 grid gap-1.5 text-xs">
                        <p className="inline-flex items-center gap-1.5" style={{ color: "var(--muted)" }}>
                          <KeyRound className="h-3.5 w-3.5 shrink-0" />
                          <span>Token: {item.api_token_masked || "-"}</span>
                        </p>
                        <p className="inline-flex items-center gap-1.5">
                          <Building2 className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--muted)" }} />
                          <span className="truncate">{counterpartyDisplay}</span>
                        </p>
                        <p className="inline-flex items-center gap-1.5">
                          <MapPin className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--muted)" }} />
                          <span className="truncate">{cityDisplay}</span>
                        </p>
                        <p className="inline-flex items-center gap-1.5">
                          <MapPin className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--muted)" }} />
                          <span className="truncate">{addressDisplay}</span>
                        </p>
                      </div>

                      <div className="flex shrink-0 items-center gap-1 self-end">
                        <button
                          type="button"
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          disabled={item.is_default || settingPrimaryId === item.id}
                          onClick={() => { void setPrimarySender(item.id); }}
                          aria-label={t("orders.modals.waybill.settings.form.default")}
                        >
                          <Star className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          onClick={() => openEditSender(item)}
                          aria-label={t("orders.modals.waybill.settings.actions.edit")}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                          style={{ borderColor: "#ef4444", backgroundColor: "rgba(239,68,68,.1)", color: "#b91c1c" }}
                          disabled={deletingId === item.id}
                          onClick={async () => {
                            if (!token) {
                              return;
                            }
                            setDeletingId(item.id);
                            try {
                              await deleteBackofficeNovaPoshtaSenderProfile(token, item.id);
                              showSuccess(t("orders.messages.senderDeleted"));
                              if (editingId === item.id) {
                                closeEditor();
                              }
                              await refetch();
                            } catch (err: unknown) {
                              showApiError(err, t("orders.messages.senderDeleteFailed"));
                            } finally {
                              setDeletingId(null);
                            }
                          }}
                          aria-label={t("orders.modals.waybill.settings.actions.delete")}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </article>
                );
                })}
              </div>
            </AsyncState>
          </div>
        </div>

        <aside className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <div className="mb-3">
            <h3 className="text-sm font-semibold">{t("orders.modals.waybill.settings.lookup.title")}</h3>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
              {t("orders.modals.waybill.settings.lookup.subtitle")}
            </p>
          </div>

          <div className="mt-3 grid gap-3">
            <div className="rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <p className="mb-1 text-xs font-semibold">{t("orders.modals.waybill.settings.lookup.settlements")}</p>
              <div ref={settlementLookupRootRef} className="relative">
                <input
                  className="h-9 w-full rounded-md border px-2 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  value={settlementQuery}
                  onChange={(e) => {
                    const next = e.target.value;
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
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      setSettlements([]);
                      setActiveSettlementIndex(-1);
                      return;
                    }
                    if (!settlements.length) {
                      return;
                    }
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setActiveSettlementIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, settlements.length - 1)));
                      return;
                    }
                    if (event.key === "ArrowUp") {
                      event.preventDefault();
                      setActiveSettlementIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                      return;
                    }
                    if (event.key === "Enter") {
                      event.preventDefault();
                      const resolvedIndex = activeSettlementIndex >= 0 ? activeSettlementIndex : 0;
                      const selected = settlements[resolvedIndex];
                      if (selected) {
                        applySettlementLookup(selected);
                      }
                    }
                  }}
                  placeholder={t("orders.modals.waybill.settings.lookup.searchPlaceholder")}
                />
                {settlements.length ? (
                  <div
                    className="absolute left-0 right-0 top-10 z-20 max-h-44 overflow-auto rounded-md border"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    role="listbox"
                    aria-label={t("orders.modals.waybill.settings.lookup.settlements")}
                  >
                    {settlements.map((row, index) => (
                      <button
                        key={row.ref}
                        type="button"
                        data-nav-scope="lookup-settlement"
                        data-nav-index={index}
                        className="flex h-9 w-full items-center border-b px-2 text-left text-xs last:border-b-0"
                        style={{
                          borderColor: "var(--border)",
                          backgroundColor: index === activeSettlementIndex ? "var(--surface-2)" : "var(--surface)",
                        }}
                        role="option"
                        aria-selected={index === activeSettlementIndex}
                        onMouseEnter={() => setActiveSettlementIndex(index)}
                        onClick={() => applySettlementLookup(row)}
                      >
                        <span className="truncate font-medium">{row.label}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
              <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
                {!canLookup
                  ? "Выберите отправителя с токеном."
                  : settlementLoading
                    ? "Ищем города..."
                    : "Введите минимум 2 символа."}
              </p>
            </div>

            <div className="rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <p className="mb-1 text-xs font-semibold">{t("orders.modals.waybill.settings.lookup.streets")}</p>
              <div ref={streetLookupRootRef} className="relative">
                <input
                  className="h-9 w-full rounded-md border px-2 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  value={streetQuery}
                  onChange={(e) => setStreetQuery(e.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      setStreets([]);
                      setActiveStreetIndex(-1);
                      return;
                    }
                    if (!streets.length) {
                      return;
                    }
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setActiveStreetIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, streets.length - 1)));
                      return;
                    }
                    if (event.key === "ArrowUp") {
                      event.preventDefault();
                      setActiveStreetIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                      return;
                    }
                    if (event.key === "Enter") {
                      event.preventDefault();
                      const resolvedIndex = activeStreetIndex >= 0 ? activeStreetIndex : 0;
                      const selected = streets[resolvedIndex];
                      if (selected) {
                        applyStreetLookup(selected);
                      }
                    }
                  }}
                  placeholder={t("orders.modals.waybill.settings.lookup.searchPlaceholder")}
                />
                {streets.length ? (
                  <div
                    className="absolute left-0 right-0 top-10 z-20 max-h-44 overflow-auto rounded-md border"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    role="listbox"
                    aria-label={t("orders.modals.waybill.settings.lookup.streets")}
                  >
                    {streets.map((row, index) => (
                      <button
                        key={row.street_ref}
                        type="button"
                        data-nav-scope="lookup-street"
                        data-nav-index={index}
                        className="flex h-9 w-full items-center border-b px-2 text-left text-xs last:border-b-0"
                        style={{
                          borderColor: "var(--border)",
                          backgroundColor: index === activeStreetIndex ? "var(--surface-2)" : "var(--surface)",
                        }}
                        role="option"
                        aria-selected={index === activeStreetIndex}
                        onMouseEnter={() => setActiveStreetIndex(index)}
                        onClick={() => applyStreetLookup(row)}
                      >
                        <span className="truncate font-medium">{row.label}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
              <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
                {!canLookup
                  ? "Выберите отправителя с токеном."
                  : !lookupSettlementRef
                    ? "Сначала выберите город."
                    : streetLoading
                      ? "Ищем улицы..."
                      : "Введите минимум 2 символа."}
              </p>
            </div>

            <div className="rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <p className="mb-1 text-xs font-semibold">{t("orders.modals.waybill.settings.lookup.warehouses")}</p>
              <div ref={warehouseLookupRootRef} className="relative">
                <input
                  className="h-9 w-full rounded-md border px-2 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                  value={warehouseQuery}
                  onChange={(e) => setWarehouseQuery(e.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      setWarehouses([]);
                      setActiveWarehouseIndex(-1);
                      return;
                    }
                    if (!warehouses.length) {
                      return;
                    }
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setActiveWarehouseIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, warehouses.length - 1)));
                      return;
                    }
                    if (event.key === "ArrowUp") {
                      event.preventDefault();
                      setActiveWarehouseIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                      return;
                    }
                    if (event.key === "Enter") {
                      event.preventDefault();
                      const resolvedIndex = activeWarehouseIndex >= 0 ? activeWarehouseIndex : 0;
                      const selected = warehouses[resolvedIndex];
                      if (selected) {
                        applyWarehouseLookup(selected);
                      }
                    }
                  }}
                  placeholder={t("orders.modals.waybill.settings.lookup.searchPlaceholder")}
                />
                {warehouses.length ? (
                  <div
                    className="absolute left-0 right-0 top-10 z-20 max-h-44 overflow-auto rounded-md border"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    role="listbox"
                    aria-label={t("orders.modals.waybill.settings.lookup.warehouses")}
                  >
                    {warehouses.map((row, index) => {
                      const formatted = formatWarehouseLookupDisplay(row);
                      return (
                        <button
                          key={row.ref}
                          type="button"
                          data-nav-scope="lookup-warehouse"
                          data-nav-index={index}
                          className="flex h-10 w-full items-center border-b px-2 text-left text-xs last:border-b-0"
                          style={{
                            borderColor: "var(--border)",
                            backgroundColor: index === activeWarehouseIndex ? "var(--surface-2)" : "var(--surface)",
                          }}
                          role="option"
                          aria-selected={index === activeWarehouseIndex}
                          onMouseEnter={() => setActiveWarehouseIndex(index)}
                          onClick={() => applyWarehouseLookup(row)}
                        >
                          <span className="truncate font-medium">{formatted.label}</span>
                          {formatted.subtitle ? (
                            <span className="ml-2 shrink-0 text-[11px]" style={{ color: "var(--muted)" }}>
                              {formatted.subtitle}
                            </span>
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
              <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
                {!canLookup
                  ? "Выберите отправителя с токеном."
                  : !lookupCityRef
                    ? "Сначала выберите город."
                    : warehouseLoading
                      ? "Ищем отделения/почтоматы..."
                      : "Цифры: от 1 символа, текст: от 2 символов."}
              </p>
            </div>
          </div>
        </aside>
      </div>

      {isEditorOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label={t("orders.actions.closeModal")} onClick={closeEditor} />
          <form
            className="relative z-10 w-full max-w-2xl rounded-xl border p-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={(event) => event.stopPropagation()}
            onSubmit={(event) => {
              event.preventDefault();
              void submitForm();
            }}
          >
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">
                {editingId ? t("orders.modals.waybill.settings.actions.update") : t("orders.modals.waybill.settings.actions.create")}
              </h3>
              <button
                type="button"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                aria-label={t("orders.actions.closeModal")}
                onClick={closeEditor}
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid gap-2 md:grid-cols-2">
              <div className="md:col-span-2">
                <div className="flex gap-2">
                  <input
                    className="h-10 min-w-0 flex-1 rounded-md border px-3 text-sm"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    placeholder={editingId ? `${t("orders.modals.waybill.settings.form.apiToken")} (optional)` : t("orders.modals.waybill.settings.form.apiToken")}
                    value={form.api_token}
                    onChange={(e) => setForm((prev) => ({ ...prev, api_token: e.target.value }))}
                  />
                  <button
                    type="button"
                    className="inline-flex h-10 shrink-0 items-center rounded-md border px-3 text-xs font-semibold"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    onClick={() => { void saveTokenOnly(); }}
                    disabled={savingTokenOnly}
                  >
                    {savingTokenOnly ? t("loading") : "Сохранить токен"}
                  </button>
                </div>
                {editingId ? (
                  <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                    Текущий токен: {rows.find((row) => row.id === editingId)?.api_token_masked || "не сохранён"}
                  </p>
                ) : (
                  <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                    Сохраните токен, затем заполните поля отправителя и нажмите сохранить профиль.
                  </p>
                )}
              </div>
              <div ref={counterpartyLookupRootRef} className="relative">
                <input
                  className="h-10 w-full rounded-md border px-3 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  placeholder="Контрагент"
                  value={counterpartyQuery}
                  onChange={(e) => {
                    const next = e.target.value;
                    setCounterpartyQuery(next);
                    setForm((prev) => ({ ...prev, counterparty_ref: next }));
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      setCounterparties([]);
                      setActiveCounterpartyIndex(-1);
                      return;
                    }
                    if (!counterparties.length) {
                      return;
                    }
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setActiveCounterpartyIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, counterparties.length - 1)));
                      return;
                    }
                    if (event.key === "ArrowUp") {
                      event.preventDefault();
                      setActiveCounterpartyIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                      return;
                    }
                    if (event.key === "Enter") {
                      event.preventDefault();
                      const resolvedIndex = activeCounterpartyIndex >= 0 ? activeCounterpartyIndex : 0;
                      const selected = counterparties[resolvedIndex];
                      if (selected) {
                        void applyCounterparty(selected);
                      }
                    }
                  }}
                />
                {counterparties.length ? (
                  <div
                    className="absolute left-0 right-0 top-11 z-20 max-h-40 overflow-auto rounded-md border"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    role="listbox"
                    aria-label="Контрагенты"
                  >
                    {counterparties.map((row, index) => (
                      <button
                        key={row.ref}
                        type="button"
                        data-nav-scope="counterparty"
                        data-nav-index={index}
                        className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
                        style={{
                          borderColor: "var(--border)",
                          backgroundColor: index === activeCounterpartyIndex ? "var(--surface-2)" : "var(--surface)",
                        }}
                        role="option"
                        aria-selected={index === activeCounterpartyIndex}
                        onMouseEnter={() => setActiveCounterpartyIndex(index)}
                        onClick={() => { void applyCounterparty(row); }}
                      >
                        <span className="truncate font-medium">{row.label}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
                <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
                  {!editingId
                    ? "Сначала сохраните токен отправителя."
                    : counterpartyLoading
                      ? "Ищем контрагентов..."
                      : counterpartyDetailsLoading
                        ? "Подтягиваем телефон и адрес..."
                      : form.counterparty_ref
                        ? "Контрагент выбран."
                        : "Введите минимум 2 символа для поиска."}
                </p>
              </div>
              <input className="h-10 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} placeholder={t("orders.modals.waybill.settings.form.phone")} value={form.phone} onChange={(e) => setForm((prev) => ({ ...prev, phone: e.target.value }))} />
              <input className="h-10 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} placeholder="ФИО" value={form.contact_name} onChange={(e) => setForm((prev) => ({ ...prev, contact_name: e.target.value }))} />
              <div ref={modalCityLookupRootRef} className="relative">
                <input
                  className="h-10 w-full rounded-md border px-3 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  placeholder="Город"
                  value={modalCityQuery}
                  onChange={(e) => {
                    const next = e.target.value;
                    setModalCityQuery(next);
                    setForm((prev) => ({ ...prev, city_ref: "" }));
                    setSelectedSettlementRef("");
                    setModalAddresses([]);
                    setActiveModalAddressIndex(-1);
                    setModalAddressQuery("");
                    setSelectedModalAddressRef("");
                    setSelectedModalAddressLabel("");
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      setModalCities([]);
                      setActiveModalCityIndex(-1);
                      return;
                    }
                    if (!modalCities.length) {
                      return;
                    }
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setActiveModalCityIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, modalCities.length - 1)));
                      return;
                    }
                    if (event.key === "ArrowUp") {
                      event.preventDefault();
                      setActiveModalCityIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                      return;
                    }
                    if (event.key === "Enter") {
                      event.preventDefault();
                      const resolvedIndex = activeModalCityIndex >= 0 ? activeModalCityIndex : 0;
                      const selected = modalCities[resolvedIndex];
                      if (selected) {
                        applyModalCity(selected);
                      }
                    }
                  }}
                />
                {modalCities.length ? (
                  <div
                    className="absolute left-0 right-0 top-11 z-20 max-h-48 overflow-auto rounded-md border"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    role="listbox"
                    aria-label="Города"
                  >
                    {modalCities.map((item, index) => (
                      <button
                        key={item.ref}
                        type="button"
                        data-nav-scope="modal-city"
                        data-nav-index={index}
                        className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
                        style={{
                          borderColor: "var(--border)",
                          backgroundColor: index === activeModalCityIndex ? "var(--surface-2)" : "var(--surface)",
                        }}
                        role="option"
                        aria-selected={index === activeModalCityIndex}
                        onMouseEnter={() => setActiveModalCityIndex(index)}
                        onClick={() => applyModalCity(item)}
                      >
                        <span className="truncate font-medium">{item.label}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
                <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
                  {!editingId ? "Сначала сохраните токен отправителя." : modalCityLoading ? "Ищем города..." : "Введите минимум 2 символа."}
                </p>
              </div>
              <div ref={modalAddressLookupRootRef} className="relative md:col-span-2">
                <input
                  className="h-10 w-full rounded-md border px-3 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  placeholder="Отделение / почтомат / адрес"
                  value={modalAddressQuery}
                  onChange={(e) => {
                    const next = e.target.value;
                    setModalAddressQuery(next);
                    setModalAddresses([]);
                    setActiveModalAddressIndex(-1);
                    const basePart = next.split(",")[0]?.trim().toLowerCase() ?? "";
                    const selectedBase = selectedModalAddressLabel.trim().toLowerCase();
                    const keepSelectedRef = Boolean(selectedModalAddressRef && selectedBase && basePart === selectedBase);
                    if (keepSelectedRef) {
                      setForm((prev) => ({ ...prev, address_ref: selectedModalAddressRef }));
                      return;
                    }
                    setSelectedModalAddressRef("");
                    setSelectedModalAddressLabel("");
                    setForm((prev) => ({ ...prev, address_ref: next }));
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      setModalAddresses([]);
                      setActiveModalAddressIndex(-1);
                      return;
                    }
                    if (!modalAddresses.length) {
                      return;
                    }
                    if (event.key === "ArrowDown") {
                      event.preventDefault();
                      setActiveModalAddressIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, modalAddresses.length - 1)));
                      return;
                    }
                    if (event.key === "ArrowUp") {
                      event.preventDefault();
                      setActiveModalAddressIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                      return;
                    }
                    if (event.key === "Enter") {
                      event.preventDefault();
                      const resolvedIndex = activeModalAddressIndex >= 0 ? activeModalAddressIndex : 0;
                      const selected = modalAddresses[resolvedIndex];
                      if (selected) {
                        applyModalAddress(selected);
                      }
                    }
                  }}
                />
                {modalAddresses.length ? (
                  <div
                    className="absolute left-0 right-0 top-11 z-20 max-h-48 overflow-auto rounded-md border"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                    role="listbox"
                    aria-label="Отделения и адреса"
                  >
                    {modalAddresses.map((item, index) => (
                      <button
                        key={item.ref}
                        type="button"
                        data-nav-scope="modal-address"
                        data-nav-index={index}
                        className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
                        style={{
                          borderColor: "var(--border)",
                          backgroundColor: index === activeModalAddressIndex ? "var(--surface-2)" : "var(--surface)",
                        }}
                        role="option"
                        aria-selected={index === activeModalAddressIndex}
                        onMouseEnter={() => setActiveModalAddressIndex(index)}
                        onClick={() => applyModalAddress(item)}
                      >
                        <span className="truncate font-medium">{item.label}</span>
                        {item.subtitle ? (
                          <span className="ml-2 shrink-0 text-[11px]" style={{ color: "var(--muted)" }}>
                            {item.subtitle}
                          </span>
                        ) : null}
                      </button>
                    ))}
                  </div>
                ) : null}
                <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
                  {!editingId
                    ? "Сначала сохраните токен отправителя."
                    : modalAddressLoading
                        ? "Ищем отделения/почтоматы/адреса..."
                        : "Цифры: отделения/почтоматы. Буквы: улицы. Дом укажите после запятой."}
                </p>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-end gap-2">
              <div className="mr-auto flex items-center gap-2">
                <label
                  className="inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold"
                  style={{
                    borderColor: form.is_active ? "#16a34a" : "var(--border)",
                    backgroundColor: form.is_active ? "#166534" : "var(--surface-2)",
                    color: form.is_active ? "#ffffff" : "var(--text)",
                  }}
                >
                  <input
                    type="checkbox"
                    className="mr-2 h-3.5 w-3.5"
                    checked={form.is_active}
                    style={{ accentColor: "#22c55e" }}
                    onChange={(e) => setForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                  />
                  {t("orders.modals.waybill.settings.form.active")}
                </label>
                <label
                  className="inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold"
                  style={{
                    borderColor: form.is_default ? "#2563eb" : "var(--border)",
                    backgroundColor: form.is_default ? "#1d4ed8" : "var(--surface-2)",
                    color: form.is_default ? "#ffffff" : "var(--text)",
                  }}
                >
                  <input
                    type="checkbox"
                    className="mr-2 h-3.5 w-3.5"
                    checked={form.is_default}
                    style={{ accentColor: "#3b82f6" }}
                    onChange={(e) => setForm((prev) => ({ ...prev, is_default: e.target.checked }))}
                  />
                  {t("orders.modals.waybill.settings.form.default")}
                </label>
              </div>
              <button
                type="submit"
                className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold"
                style={{ borderColor: "var(--border)", backgroundColor: "#2563eb", color: "#fff" }}
                disabled={saving}
              >
                <Plus className="h-4 w-4" />
                {saving ? t("loading") : editingId ? t("orders.modals.waybill.settings.actions.update") : t("orders.modals.waybill.settings.actions.create")}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </section>
  );
}
