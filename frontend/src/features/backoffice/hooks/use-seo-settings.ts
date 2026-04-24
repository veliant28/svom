"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createBackofficeSeoOverride,
  createBackofficeSeoTemplate,
  deleteBackofficeSeoOverride,
  deleteBackofficeSeoTemplate,
  getBackofficeSeoOverrides,
  getBackofficeSeoSettings,
  getBackofficeSeoTemplates,
  previewBackofficeRobots,
  rebuildBackofficeSitemap,
  updateBackofficeSeoOverride,
  updateBackofficeSeoSettings,
  updateBackofficeSeoTemplate,
} from "@/features/backoffice/api/seo-api";
import type {
  BackofficeSeoMetaOverride,
  BackofficeSeoMetaTemplate,
  BackofficeSeoSettings,
  BackofficeSeoSitemapRebuildResponse,
} from "@/features/backoffice/api/seo-api.types";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useAuth } from "@/features/auth/hooks/use-auth";

export function useSeoSettings({ t }: { t: (key: string, values?: Record<string, string | number | Date>) => string }) {
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [settings, setSettings] = useState<BackofficeSeoSettings | null>(null);
  const [templates, setTemplates] = useState<BackofficeSeoMetaTemplate[]>([]);
  const [overrides, setOverrides] = useState<BackofficeSeoMetaOverride[]>([]);
  const [robotsPreview, setRobotsPreview] = useState<string>("");
  const [lastSitemapResult, setLastSitemapResult] = useState<BackofficeSeoSitemapRebuildResponse | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [isSavingRobots, setIsSavingRobots] = useState(false);
  const [isRebuildingSitemap, setIsRebuildingSitemap] = useState(false);
  const [activeTemplateActionId, setActiveTemplateActionId] = useState<string | null>(null);
  const [activeOverrideActionId, setActiveOverrideActionId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setLoadError(null);
    try {
      const [nextSettings, templatesPayload, overridesPayload, robotsPayload] = await Promise.all([
        getBackofficeSeoSettings(token),
        getBackofficeSeoTemplates(token),
        getBackofficeSeoOverrides(token),
        previewBackofficeRobots(token),
      ]);
      setSettings(nextSettings);
      setTemplates(templatesPayload.results || []);
      setOverrides(overridesPayload.results || []);
      setRobotsPreview(robotsPayload.robots_txt || "");
    } catch (error) {
      setLoadError(showApiError(error, t("seo.messages.loadFailed")));
    } finally {
      setIsLoading(false);
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const saveSettings = useCallback(
    async (payload: Partial<BackofficeSeoSettings>) => {
      if (!token || isSavingSettings) {
        return null;
      }
      setIsSavingSettings(true);
      try {
        const updated = await updateBackofficeSeoSettings(token, payload);
        setSettings(updated);
        showSuccess(t("seo.messages.settingsSaved"));
        return updated;
      } catch (error) {
        showApiError(error, t("seo.messages.actionFailed"));
        return null;
      } finally {
        setIsSavingSettings(false);
      }
    },
    [isSavingSettings, showApiError, showSuccess, t, token],
  );

  const saveRobots = useCallback(
    async (robotsTxt: string) => {
      if (!token || isSavingRobots) {
        return null;
      }
      setIsSavingRobots(true);
      try {
        const updated = await updateBackofficeSeoSettings(token, { robots_txt: robotsTxt });
        setSettings(updated);
        const preview = await previewBackofficeRobots(token);
        setRobotsPreview(preview.robots_txt || "");
        showSuccess(t("seo.messages.settingsSaved"));
        return updated;
      } catch (error) {
        showApiError(error, t("seo.messages.actionFailed"));
        return null;
      } finally {
        setIsSavingRobots(false);
      }
    },
    [isSavingRobots, showApiError, showSuccess, t, token],
  );

  const rebuildSitemap = useCallback(async () => {
    if (!token || isRebuildingSitemap) {
      return null;
    }
    setIsRebuildingSitemap(true);
    try {
      const result = await rebuildBackofficeSitemap(token);
      setLastSitemapResult(result);
      await load();
      showSuccess(t("seo.messages.sitemapRebuilt"));
      return result;
    } catch (error) {
      showApiError(error, t("seo.messages.actionFailed"));
      return null;
    } finally {
      setIsRebuildingSitemap(false);
    }
  }, [isRebuildingSitemap, load, showApiError, showSuccess, t, token]);

  const createTemplate = useCallback(async (payload: Parameters<typeof createBackofficeSeoTemplate>[1]) => {
    if (!token) {
      return null;
    }
    setActiveTemplateActionId("create");
    try {
      const created = await createBackofficeSeoTemplate(token, payload);
      setTemplates((prev) => [...prev, created].sort((a, b) => `${a.entity_type}:${a.locale}`.localeCompare(`${b.entity_type}:${b.locale}`)));
      showSuccess(t("seo.messages.templateCreated"));
      return created;
    } catch (error) {
      showApiError(error, t("seo.messages.actionFailed"));
      return null;
    } finally {
      setActiveTemplateActionId(null);
    }
  }, [showApiError, showSuccess, t, token]);

  const updateTemplate = useCallback(async (id: string, payload: Parameters<typeof updateBackofficeSeoTemplate>[2]) => {
    if (!token) {
      return null;
    }
    setActiveTemplateActionId(id);
    try {
      const updated = await updateBackofficeSeoTemplate(token, id, payload);
      setTemplates((prev) => prev.map((item) => (item.id === id ? updated : item)));
      showSuccess(t("seo.messages.templateUpdated"));
      return updated;
    } catch (error) {
      showApiError(error, t("seo.messages.actionFailed"));
      return null;
    } finally {
      setActiveTemplateActionId(null);
    }
  }, [showApiError, showSuccess, t, token]);

  const deleteTemplate = useCallback(async (id: string) => {
    if (!token) {
      return false;
    }
    setActiveTemplateActionId(id);
    try {
      await deleteBackofficeSeoTemplate(token, id);
      setTemplates((prev) => prev.filter((item) => item.id !== id));
      showSuccess(t("seo.messages.templateDeleted"));
      return true;
    } catch (error) {
      showApiError(error, t("seo.messages.actionFailed"));
      return false;
    } finally {
      setActiveTemplateActionId(null);
    }
  }, [showApiError, showSuccess, t, token]);

  const createOverride = useCallback(async (payload: Parameters<typeof createBackofficeSeoOverride>[1]) => {
    if (!token) {
      return null;
    }
    setActiveOverrideActionId("create");
    try {
      const created = await createBackofficeSeoOverride(token, payload);
      setOverrides((prev) => [...prev, created].sort((a, b) => `${a.path}:${a.locale}`.localeCompare(`${b.path}:${b.locale}`)));
      showSuccess(t("seo.messages.overrideCreated"));
      return created;
    } catch (error) {
      showApiError(error, t("seo.messages.actionFailed"));
      return null;
    } finally {
      setActiveOverrideActionId(null);
    }
  }, [showApiError, showSuccess, t, token]);

  const updateOverride = useCallback(async (id: string, payload: Parameters<typeof updateBackofficeSeoOverride>[2]) => {
    if (!token) {
      return null;
    }
    setActiveOverrideActionId(id);
    try {
      const updated = await updateBackofficeSeoOverride(token, id, payload);
      setOverrides((prev) => prev.map((item) => (item.id === id ? updated : item)));
      showSuccess(t("seo.messages.overrideUpdated"));
      return updated;
    } catch (error) {
      showApiError(error, t("seo.messages.actionFailed"));
      return null;
    } finally {
      setActiveOverrideActionId(null);
    }
  }, [showApiError, showSuccess, t, token]);

  const deleteOverride = useCallback(async (id: string) => {
    if (!token) {
      return false;
    }
    setActiveOverrideActionId(id);
    try {
      await deleteBackofficeSeoOverride(token, id);
      setOverrides((prev) => prev.filter((item) => item.id !== id));
      showSuccess(t("seo.messages.overrideDeleted"));
      return true;
    } catch (error) {
      showApiError(error, t("seo.messages.actionFailed"));
      return false;
    } finally {
      setActiveOverrideActionId(null);
    }
  }, [showApiError, showSuccess, t, token]);

  return {
    settings,
    templates,
    overrides,
    robotsPreview,
    lastSitemapResult,
    isLoading,
    loadError,
    isSavingSettings,
    isSavingRobots,
    isRebuildingSitemap,
    activeTemplateActionId,
    activeOverrideActionId,
    reload: load,
    saveSettings,
    saveRobots,
    rebuildSitemap,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    createOverride,
    updateOverride,
    deleteOverride,
  };
}
