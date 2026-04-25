import { useCallback, type Dispatch, type SetStateAction } from "react";

import {
  createBackofficeNovaPoshtaSenderProfile,
  deleteBackofficeNovaPoshtaSenderProfile,
  listBackofficeNovaPoshtaSenderProfiles,
  updateBackofficeNovaPoshtaSenderProfile,
} from "@/features/backoffice/api/orders-api";
import {
  DRAFT_SENDER_NAME,
  getRawMetaString,
  isRefLike,
  isUuidLike,
  resolveSenderTypeFromHints,
  type NovaPoshtaSenderFormState,
} from "@/features/backoffice/components/orders/nova-poshta-senders.helpers";
import type { BackofficeNovaPoshtaSenderProfile } from "@/features/backoffice/types/nova-poshta.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

type FeedbackHandlers = {
  showApiError: (error: unknown, fallbackMessage?: string) => void;
  showSuccess: (message: string) => void;
  showWarning: (message: string) => void;
};

export function useNovaPoshtaSendersProfileActions({
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
}: {
  token: string | null;
  rows: BackofficeNovaPoshtaSenderProfile[];
  form: NovaPoshtaSenderFormState;
  editingId: string | null;
  saving: boolean;
  savingTokenOnly: boolean;
  settingPrimaryId: string | null;
  counterpartyQuery: string;
  counterpartyTypeDraft: string;
  ownershipFormDraft: string;
  edrpouDraft: string;
  contactRefDraft: string;
  modalCityQuery: string;
  modalAddressQuery: string;
  selectedSettlementRef: string;
  t: Translator;
  setForm: Dispatch<SetStateAction<NovaPoshtaSenderFormState>>;
  setEditingId: Dispatch<SetStateAction<string | null>>;
  setSaving: Dispatch<SetStateAction<boolean>>;
  setSavingTokenOnly: Dispatch<SetStateAction<boolean>>;
  setSettingPrimaryId: Dispatch<SetStateAction<string | null>>;
  setDeletingId: Dispatch<SetStateAction<string | null>>;
  closeEditor: () => void;
  refetch: () => Promise<void>;
} & FeedbackHandlers) {
  const enforceSingleDefaultSender = useCallback(async (preferredDefaultId: string) => {
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
  }, [token]);

  const submitForm = useCallback(async () => {
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
  }, [
    closeEditor,
    contactRefDraft,
    counterpartyQuery,
    counterpartyTypeDraft,
    editingId,
    edrpouDraft,
    enforceSingleDefaultSender,
    form,
    modalAddressQuery,
    modalCityQuery,
    ownershipFormDraft,
    refetch,
    rows,
    saving,
    selectedSettlementRef,
    setSaving,
    showApiError,
    showSuccess,
    showWarning,
    t,
    token,
  ]);

  const saveTokenOnly = useCallback(async () => {
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
  }, [
    editingId,
    form.address_ref,
    form.api_token,
    form.contact_name,
    form.counterparty_ref,
    form.city_ref,
    form.phone,
    refetch,
    savingTokenOnly,
    setEditingId,
    setForm,
    setSavingTokenOnly,
    showApiError,
    showSuccess,
    showWarning,
    t,
    token,
  ]);

  const setPrimarySender = useCallback(async (senderId: string) => {
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
  }, [
    enforceSingleDefaultSender,
    refetch,
    setSettingPrimaryId,
    settingPrimaryId,
    showApiError,
    showSuccess,
    t,
    token,
  ]);

  const deleteSender = useCallback(async (item: BackofficeNovaPoshtaSenderProfile) => {
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
  }, [closeEditor, editingId, refetch, setDeletingId, showApiError, showSuccess, t, token]);

  return {
    submitForm,
    saveTokenOnly,
    setPrimarySender,
    deleteSender,
  };
}
