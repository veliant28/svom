"use client";

import { useEffect, useMemo, useState } from "react";

import {
  getBackofficeIntegrationCenterState,
  patchBackofficeIntegrationCenterAutoDbRemote,
  patchBackofficeIntegrationCenterReturnsSettings,
  patchBackofficeIntegrationCenterToggle,
  patchBackofficeIntegrationCenterTranslator,
  postBackofficeIntegrationCenterAutoDbRemoteTestConnection,
  type ReturnsSettingsPatchPayload,
} from "@/features/backoffice/api/integration-center-api";
import type {
  BackofficeAutoDbRemoteState,
  BackofficeIntegrationCenterState,
  BackofficeIntegrationCenterResponse,
  BackofficeIntegrationTranslatorState,
  BackofficeReturnsSettingsState,
  IntegrationCenterToggleKey,
  IntegrationTranslatorProvider,
} from "@/features/backoffice/types/integration-center.types";

type AutoDbRemoteField = "remote_host" | "remote_port" | "remote_database" | "remote_user" | "remote_password" | "image_base_url";
type Translator = (key: string, values?: Record<string, string | number>) => string;

export function useIntegrationCenterCore({
  token,
  t,
  showApiError,
  showSuccess,
}: {
  token: string | null;
  t: Translator;
  showApiError: (error: unknown, fallbackMessage: string) => string;
  showSuccess: (message: string) => void;
}) {
  const [state, setState] = useState<BackofficeIntegrationCenterState | null>(null);
  const [translator, setTranslator] = useState<BackofficeIntegrationTranslatorState | null>(null);
  const [autodbRemote, setAutodbRemote] = useState<BackofficeAutoDbRemoteState | null>(null);
  const [returnsSettings, setReturnsSettings] = useState<BackofficeReturnsSettingsState | null>(null);
  const [googleApiKey, setGoogleApiKey] = useState("");
  const [autodbDraft, setAutodbDraft] = useState<Record<AutoDbRemoteField, string>>({
    remote_host: "",
    remote_port: "",
    remote_database: "",
    remote_user: "",
    remote_password: "",
    image_base_url: "",
  });
  const [autodbDirty, setAutodbDirty] = useState<Record<AutoDbRemoteField, boolean>>({
    remote_host: false,
    remote_port: false,
    remote_database: false,
    remote_user: false,
    remote_password: false,
    image_base_url: false,
  });
  const [isUpdatingTranslatorProvider, setIsUpdatingTranslatorProvider] = useState(false);
  const [isUpdatingGoogleApiKey, setIsUpdatingGoogleApiKey] = useState(false);
  const [updatingAutoDbFields, setUpdatingAutoDbFields] = useState<Record<AutoDbRemoteField, boolean>>({
    remote_host: false,
    remote_port: false,
    remote_database: false,
    remote_user: false,
    remote_password: false,
    image_base_url: false,
  });
  const [copiedField, setCopiedField] = useState<AutoDbRemoteField | "google_api_key" | null>(null);
  const [isTestingAutoDbConnection, setIsTestingAutoDbConnection] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingKeys, setUpdatingKeys] = useState<Record<string, boolean>>({});

  function applyResponse(payload: BackofficeIntegrationCenterResponse) {
    setState(payload.state);
    setTranslator(payload.translator);
    setAutodbRemote(payload.autodb_remote);
    setReturnsSettings(payload.returns);
  }

  useEffect(() => {
    async function load() {
      if (!token) {
        setIsLoading(false);
        setError(null);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const payload = await getBackofficeIntegrationCenterState(token);
        applyResponse(payload);
      } catch (loadError) {
        setError(showApiError(loadError, t("integrationCenter.messages.loadFailed")));
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [showApiError, t, token]);

  useEffect(() => {
    setGoogleApiKey("");
  }, [translator?.google_api_key_masked]);

  useEffect(() => {
    if (!autodbRemote) {
      return;
    }
    setAutodbDraft({
      remote_host: autodbRemote.remote_host || "",
      remote_port: String(autodbRemote.remote_port || 3306),
      remote_database: autodbRemote.remote_database || "",
      remote_user: autodbRemote.remote_user || "",
      remote_password: autodbRemote.remote_password || "",
      image_base_url: autodbRemote.image_base_url || "",
    });
    setAutodbDirty({
      remote_host: false,
      remote_port: false,
      remote_database: false,
      remote_user: false,
      remote_password: false,
      image_base_url: false,
    });
  }, [autodbRemote]);

  const isEmpty = useMemo(() => !state || Object.keys(state).length === 0, [state]);

  async function handleToggle(key: IntegrationCenterToggleKey, enabled: boolean) {
    if (!token || !state || updatingKeys[key]) {
      return;
    }
    const previousState = state;
    setUpdatingKeys((prev) => ({ ...prev, [key]: true }));
    setState({ ...state, [key]: enabled });
    try {
      const payload = await patchBackofficeIntegrationCenterToggle(token, key, enabled);
      applyResponse(payload);
      if (key === "returns.enabled") {
        showSuccess(
          enabled
            ? t("integrationCenter.messages.returnsServiceEnabled")
            : t("integrationCenter.messages.returnsServiceDisabled"),
        );
      } else {
        showSuccess(t("integrationCenter.messages.updated"));
      }
    } catch (patchError) {
      setState(previousState);
      showApiError(patchError, t("integrationCenter.messages.updateFailed"));
    } finally {
      setUpdatingKeys((prev) => ({ ...prev, [key]: false }));
    }
  }

  async function handleTranslatorProvider(provider: IntegrationTranslatorProvider) {
    if (!token || !translator || isUpdatingTranslatorProvider || translator.provider === provider) {
      return;
    }
    const previous = translator;
    setIsUpdatingTranslatorProvider(true);
    setTranslator({ ...translator, provider });
    try {
      const payload = await patchBackofficeIntegrationCenterTranslator(token, { provider });
      applyResponse(payload);
      showSuccess(t("integrationCenter.messages.translatorProviderUpdated"));
    } catch (patchError) {
      setTranslator(previous);
      showApiError(patchError, t("integrationCenter.messages.translatorUpdateFailed"));
    } finally {
      setIsUpdatingTranslatorProvider(false);
    }
  }

  async function handleGoogleApiKeyCommit() {
    if (!token || isUpdatingGoogleApiKey) {
      return;
    }
    const nextKey = googleApiKey.trim();
    if (!nextKey) {
      return;
    }
    setIsUpdatingGoogleApiKey(true);
    try {
      const payload = await patchBackofficeIntegrationCenterTranslator(token, { google_api_key: nextKey });
      applyResponse(payload);
      setGoogleApiKey("");
      showSuccess(t("integrationCenter.messages.translatorTokenUpdated"));
    } catch (patchError) {
      showApiError(patchError, t("integrationCenter.messages.translatorUpdateFailed"));
    } finally {
      setIsUpdatingGoogleApiKey(false);
    }
  }

  function handleAutoDbDraftChange(field: AutoDbRemoteField, value: string) {
    setAutodbDraft((prev) => ({ ...prev, [field]: value }));
    setAutodbDirty((prev) => ({ ...prev, [field]: true }));
  }

  async function handleAutoDbRemoteCommit(field: AutoDbRemoteField) {
    if (!token || !autodbRemote || updatingAutoDbFields[field] || !autodbDirty[field]) {
      return;
    }
    const rawValue = autodbDraft[field];
    const value = rawValue.trim();
    let payload: Parameters<typeof patchBackofficeIntegrationCenterAutoDbRemote>[1] | null = null;
    if (field === "remote_port") {
      const parsed = Number.parseInt(value, 10);
      if (!Number.isFinite(parsed) || parsed < 1) {
        showApiError(new Error("invalid_port"), t("integrationCenter.messages.autodbRemoteInvalidPort"));
        return;
      }
      if (parsed === autodbRemote.remote_port) {
        setAutodbDirty((prev) => ({ ...prev, [field]: false }));
        return;
      }
      payload = { remote_port: parsed };
    } else if (field === "remote_user") {
      if (!value) {
        return;
      }
      payload = { remote_user: value };
    } else if (field === "remote_password") {
      if (!value) {
        return;
      }
      payload = { remote_password: value };
    } else {
      const current = String(autodbRemote[field] || "").trim();
      if (value === current) {
        setAutodbDirty((prev) => ({ ...prev, [field]: false }));
        return;
      }
      payload = { [field]: value } as Parameters<typeof patchBackofficeIntegrationCenterAutoDbRemote>[1];
    }
    if (!payload) {
      return;
    }

    setUpdatingAutoDbFields((prev) => ({ ...prev, [field]: true }));
    try {
      const response = await patchBackofficeIntegrationCenterAutoDbRemote(token, payload);
      applyResponse(response);
      setAutodbDirty((prev) => ({ ...prev, [field]: false }));
      showSuccess(t("integrationCenter.messages.autodbRemoteUpdated"));
    } catch (patchError) {
      showApiError(patchError, t("integrationCenter.messages.autodbRemoteUpdateFailed"));
    } finally {
      setUpdatingAutoDbFields((prev) => ({ ...prev, [field]: false }));
    }
  }

  async function handleCopyField(field: AutoDbRemoteField | "google_api_key", value: string) {
    const clean = String(value || "").trim();
    if (!clean) {
      showApiError(new Error("empty_value"), t("integrationCenter.messages.copyEmpty"));
      return;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(clean);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = clean;
        textarea.setAttribute("readonly", "true");
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(textarea);
        if (!copied) {
          throw new Error("copy_fallback_failed");
        }
      }
      setCopiedField(field);
      showSuccess(t("integrationCenter.messages.copySuccess"));
      setTimeout(() => setCopiedField((current) => (current === field ? null : current)), 1200);
    } catch (copyError) {
      showApiError(copyError, t("integrationCenter.messages.copyFailed"));
    }
  }

  async function handleAutoDbConnectionTest() {
    if (!token || isTestingAutoDbConnection) {
      return;
    }
    setIsTestingAutoDbConnection(true);
    try {
      const response = await postBackofficeIntegrationCenterAutoDbRemoteTestConnection(token);
      if (response.ok) {
        showSuccess(t("integrationCenter.messages.autodbRemoteConnectionOk"));
      } else {
        showApiError(new Error(response.message), response.message || t("integrationCenter.messages.autodbRemoteConnectionFailed"));
      }
    } catch (testError) {
      showApiError(testError, t("integrationCenter.messages.autodbRemoteConnectionFailed"));
    } finally {
      setIsTestingAutoDbConnection(false);
    }
  }

  async function patchReturnsSettings(payload: ReturnsSettingsPatchPayload, successMessage: string) {
    if (!token || !returnsSettings) {
      return;
    }
    const previous = returnsSettings;
    try {
      const response = await patchBackofficeIntegrationCenterReturnsSettings(token, payload);
      applyResponse(response);
      showSuccess(successMessage);
    } catch (patchError) {
      setReturnsSettings(previous);
      showApiError(patchError, t("integrationCenter.messages.returnsSaveFailed"));
    }
  }

  return {
    state,
    setState,
    translator,
    autodbRemote,
    returnsSettings,
    setReturnsSettings,
    googleApiKey,
    setGoogleApiKey,
    autodbDraft,
    updatingAutoDbFields,
    copiedField,
    isTestingAutoDbConnection,
    isUpdatingTranslatorProvider,
    isUpdatingGoogleApiKey,
    isLoading,
    error,
    isEmpty,
    updatingKeys,
    handleToggle,
    handleTranslatorProvider,
    handleGoogleApiKeyCommit,
    handleAutoDbDraftChange,
    handleAutoDbRemoteCommit,
    handleCopyField,
    handleAutoDbConnectionTest,
    patchReturnsSettings,
  };
}
