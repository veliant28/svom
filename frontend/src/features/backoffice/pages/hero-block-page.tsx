"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Save, Trash2, Upload } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  createBackofficeHeroSlide,
  deleteBackofficeHeroSlide,
  getBackofficeHeroBlockSettings,
  listBackofficeHeroSlides,
  updateBackofficeHeroBlockSettings,
  updateBackofficeHeroSlide,
} from "@/features/backoffice/api/hero-block-api";
import {
  FileField,
  ImagePreview,
  LocaleFields,
  NumberStepper,
  TextField,
  ToggleField,
} from "@/features/backoffice/components/hero-block/hero-block-form-fields";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import {
  DEFAULT_SETTINGS_FORM,
  DEFAULT_SLIDE_FORM,
  clampNumber,
  emitHeroBlockUpdated,
  hasTitle,
  sortSlides,
  toSettingsForm,
  toSlideForm,
  type SettingsForm,
  type SlideForm,
} from "@/features/backoffice/lib/hero-block-page.helpers";
import type {
  BackofficeHeroBlockEffect,
  BackofficeHeroBlockSettings,
  BackofficeHeroSlide,
} from "@/features/backoffice/types/hero-block.types";
import { useAuth } from "@/features/auth/hooks/use-auth";

export function HeroBlockPage() {
  const t = useTranslations("backoffice.common");
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [activeSlideActionId, setActiveSlideActionId] = useState<string | null>(null);

  const [settings, setSettings] = useState<BackofficeHeroBlockSettings | null>(null);
  const [settingsForm, setSettingsForm] = useState<SettingsForm>(DEFAULT_SETTINGS_FORM);
  const [slides, setSlides] = useState<BackofficeHeroSlide[]>([]);
  const [drafts, setDrafts] = useState<Record<string, SlideForm>>({});
  const [newSlide, setNewSlide] = useState<SlideForm>(DEFAULT_SLIDE_FORM);

  const getDraft = useCallback((item: BackofficeHeroSlide): SlideForm => {
    return drafts[item.id] ?? toSlideForm(item);
  }, [drafts]);

  const load = useCallback(async () => {
    if (!token) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setLoadError(null);
    try {
      const [nextSettings, listPayload] = await Promise.all([
        getBackofficeHeroBlockSettings(token),
        listBackofficeHeroSlides(token),
      ]);
      setSettings(nextSettings);
      setSettingsForm(toSettingsForm(nextSettings));
      setSlides(sortSlides(listPayload.results || []));
      setDrafts({});
    } catch (error: unknown) {
      setLoadError(showApiError(error, t("heroBlock.messages.loadFailed")));
    } finally {
      setIsLoading(false);
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const canCreate = slides.length < 10;
  const settingsDirty = useMemo(() => {
    if (!settings) {
      return false;
    }
    return (
      settings.autoplay_enabled !== settingsForm.autoplay_enabled
      || settings.transition_effect !== settingsForm.transition_effect
      || Math.round(settings.transition_interval_ms / 1000) !== settingsForm.transition_interval_seconds
      || settings.transition_speed_ms !== settingsForm.transition_speed_ms
      || settings.max_active_slides !== settingsForm.max_active_slides
    );
  }, [settings, settingsForm]);

  async function saveSettings() {
    if (!token) {
      return;
    }
    setIsSavingSettings(true);
    try {
      const payload = await updateBackofficeHeroBlockSettings(token, {
        autoplay_enabled: settingsForm.autoplay_enabled,
        transition_effect: settingsForm.transition_effect,
        transition_interval_ms: clampNumber(settingsForm.transition_interval_seconds, 1, 60) * 1000,
        transition_speed_ms: clampNumber(settingsForm.transition_speed_ms, 150, 10000),
        max_active_slides: clampNumber(settingsForm.max_active_slides, 1, 10),
      });
      setSettings(payload);
      setSettingsForm(toSettingsForm(payload));
      showSuccess(t("heroBlock.messages.settingsSaved"));
      emitHeroBlockUpdated();
    } catch (error: unknown) {
      showApiError(error, t("heroBlock.messages.settingsSaveFailed"));
    } finally {
      setIsSavingSettings(false);
    }
  }

  async function saveSlide(item: BackofficeHeroSlide) {
    if (!token) {
      return;
    }
    const draft = getDraft(item);
    setActiveSlideActionId(item.id);
    try {
      const updated = await updateBackofficeHeroSlide(token, item.id, {
        title_uk: draft.title_uk.trim(),
        title_ru: draft.title_ru.trim(),
        title_en: draft.title_en.trim(),
        subtitle_uk: draft.subtitle_uk.trim(),
        subtitle_ru: draft.subtitle_ru.trim(),
        subtitle_en: draft.subtitle_en.trim(),
        cta_url: draft.cta_url.trim(),
        sort_order: clampNumber(draft.sort_order, 1, 999),
        is_active: draft.is_active,
        desktop_image: draft.desktop_image_file || undefined,
        mobile_image: draft.mobile_image_file || undefined,
      });
      setSlides((prev) => sortSlides(prev.map((entry) => (entry.id === item.id ? updated : entry))));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      showSuccess(t("heroBlock.messages.slideSaved"));
      emitHeroBlockUpdated();
    } catch (error: unknown) {
      showApiError(error, t("heroBlock.messages.slideSaveFailed"));
    } finally {
      setActiveSlideActionId(null);
    }
  }

  async function removeSlide(item: BackofficeHeroSlide) {
    if (!token) {
      return;
    }
    setActiveSlideActionId(item.id);
    try {
      await deleteBackofficeHeroSlide(token, item.id);
      setSlides((prev) => prev.filter((entry) => entry.id !== item.id));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      showSuccess(t("heroBlock.messages.slideDeleted"));
      emitHeroBlockUpdated();
    } catch (error: unknown) {
      showApiError(error, t("heroBlock.messages.slideDeleteFailed"));
    } finally {
      setActiveSlideActionId(null);
    }
  }

  async function createSlide() {
    if (!token || !canCreate || !newSlide.desktop_image_file || !newSlide.mobile_image_file || !hasTitle(newSlide)) {
      return;
    }
    setIsCreating(true);
    try {
      const created = await createBackofficeHeroSlide(token, {
        title_uk: newSlide.title_uk.trim(),
        title_ru: newSlide.title_ru.trim(),
        title_en: newSlide.title_en.trim(),
        subtitle_uk: newSlide.subtitle_uk.trim(),
        subtitle_ru: newSlide.subtitle_ru.trim(),
        subtitle_en: newSlide.subtitle_en.trim(),
        cta_url: newSlide.cta_url.trim(),
        sort_order: clampNumber(newSlide.sort_order, 1, 999),
        is_active: newSlide.is_active,
        desktop_image: newSlide.desktop_image_file,
        mobile_image: newSlide.mobile_image_file,
      });
      setSlides((prev) => sortSlides([...prev, created]));
      setNewSlide({
        ...DEFAULT_SLIDE_FORM,
        sort_order: clampNumber(created.sort_order + 1, 1, 999),
      });
      showSuccess(t("heroBlock.messages.slideCreated"));
      emitHeroBlockUpdated();
    } catch (error: unknown) {
      showApiError(error, t("heroBlock.messages.slideCreateFailed"));
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <AsyncState isLoading={isLoading} error={loadError} empty={false} emptyLabel="">
      <section className="grid gap-4">
        <PageHeader
          title={t("heroBlock.title")}
          description={t("heroBlock.subtitle")}
          actionsBeforeLogout={(
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={() => {
                void load();
              }}
            >
              <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
              {t("heroBlock.actions.refresh")}
            </button>
          )}
        />

        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">{t("heroBlock.settings.title")}</h2>
            <span className="text-xs" style={{ color: "var(--muted)" }}>
              {t("heroBlock.settings.limitLabel", { count: slides.length, max: 10 })}
            </span>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <label className="grid min-w-[220px] gap-1">
              <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                {t("heroBlock.settings.effect")}
              </span>
              <select
                value={settingsForm.transition_effect}
                onChange={(event) => {
                  setSettingsForm((prev) => ({ ...prev, transition_effect: event.target.value as BackofficeHeroBlockEffect }));
                }}
                className="h-9 rounded-md border px-2 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              >
                <option value="crossfade">{t("heroBlock.effects.crossfade")}</option>
                <option value="pan_left">{t("heroBlock.effects.panLeft")}</option>
                <option value="lift_up">{t("heroBlock.effects.liftUp")}</option>
                <option value="cinematic_zoom">{t("heroBlock.effects.cinematicZoom")}</option>
                <option value="reveal_right">{t("heroBlock.effects.revealRight")}</option>
              </select>
            </label>

            <NumberStepper
              label={t("heroBlock.settings.intervalSeconds")}
              value={settingsForm.transition_interval_seconds}
              min={1}
              max={60}
              onChange={(next) => {
                setSettingsForm((prev) => ({ ...prev, transition_interval_seconds: next }));
              }}
            />

            <NumberStepper
              label={t("heroBlock.settings.speedMs")}
              value={settingsForm.transition_speed_ms}
              min={150}
              max={10000}
              step={50}
              onChange={(next) => {
                setSettingsForm((prev) => ({ ...prev, transition_speed_ms: next }));
              }}
            />

            <NumberStepper
              label={t("heroBlock.settings.maxActive")}
              value={settingsForm.max_active_slides}
              min={1}
              max={10}
              onChange={(next) => {
                setSettingsForm((prev) => ({ ...prev, max_active_slides: next }));
              }}
            />

            <div className="ml-auto flex flex-wrap items-end gap-3">
              <label className="grid w-[118px] gap-1">
                <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                  {t("heroBlock.settings.autoplay")}
                </span>
                <button
                  type="button"
                  className="h-9 rounded-md border px-3 text-sm font-semibold"
                  style={{
                    borderColor: settingsForm.autoplay_enabled ? "var(--text)" : "var(--border)",
                    backgroundColor: settingsForm.autoplay_enabled ? "var(--text)" : "var(--surface)",
                    color: settingsForm.autoplay_enabled ? "var(--surface)" : "var(--text)",
                  }}
                  onClick={() => {
                    setSettingsForm((prev) => ({ ...prev, autoplay_enabled: !prev.autoplay_enabled }));
                  }}
                >
                  {settingsForm.autoplay_enabled ? t("yes") : t("no")}
                </button>
              </label>
              <button
                type="button"
                disabled={!settingsDirty || isSavingSettings}
                className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                style={{
                  borderColor: !settingsDirty || isSavingSettings ? "var(--border)" : "#2563eb",
                  backgroundColor: !settingsDirty || isSavingSettings ? "var(--surface-2)" : "#2563eb",
                  color: !settingsDirty || isSavingSettings ? "var(--text)" : "#fff",
                }}
                onClick={() => {
                  void saveSettings();
                }}
              >
                <Save size={14} />
                {isSavingSettings ? t("heroBlock.actions.saving") : t("heroBlock.actions.saveSettings")}
              </button>
            </div>
          </div>
        </div>

        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <h2 className="text-sm font-semibold">{t("heroBlock.create.title")}</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
            {t("heroBlock.create.subtitle")} {t("heroBlock.create.desktopImageHint")} {t("heroBlock.create.mobileImageHint")}
          </p>

          <div className="mt-4 grid gap-4">
            <LocaleFields
              titleLabel={t("heroBlock.fields.title")}
              subtitleLabel={t("heroBlock.fields.subtitle")}
              form={newSlide}
              onChange={setNewSlide}
            />

            <div className="grid gap-3 lg:grid-cols-3">
              <TextField
                label={t("heroBlock.fields.link")}
                wrapperClassName="grid-rows-[1.1rem_2.25rem]"
                labelClassName="whitespace-nowrap overflow-hidden text-ellipsis"
                value={newSlide.cta_url}
                onChange={(next) => {
                  setNewSlide((prev) => ({ ...prev, cta_url: next }));
                }}
              />
              <FileField
                label={t("heroBlock.fields.desktopImage")}
                wrapperClassName="grid-rows-[1.1rem_2.25rem_auto]"
                labelClassName="whitespace-nowrap overflow-hidden text-ellipsis"
                selectedFile={newSlide.desktop_image_file}
                onChange={(file) => {
                  setNewSlide((prev) => ({ ...prev, desktop_image_file: file }));
                }}
              />
              <FileField
                label={t("heroBlock.fields.mobileImage")}
                wrapperClassName="grid-rows-[1.1rem_2.25rem_auto]"
                labelClassName="whitespace-nowrap overflow-hidden text-ellipsis"
                selectedFile={newSlide.mobile_image_file}
                onChange={(file) => {
                  setNewSlide((prev) => ({ ...prev, mobile_image_file: file }));
                }}
              />
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <ToggleField
                label={t("heroBlock.fields.active")}
                widthClassName="w-[118px]"
                value={newSlide.is_active}
                onToggle={() => {
                  setNewSlide((prev) => ({ ...prev, is_active: !prev.is_active }));
                }}
                yesLabel={t("yes")}
                noLabel={t("no")}
              />
              <NumberStepper
                label={t("heroBlock.fields.sortOrder")}
                value={newSlide.sort_order}
                min={1}
                max={999}
                onChange={(next) => {
                  setNewSlide((prev) => ({ ...prev, sort_order: next }));
                }}
              />
              <button
                type="button"
                disabled={!canCreate || isCreating || !newSlide.desktop_image_file || !newSlide.mobile_image_file || !hasTitle(newSlide)}
                className="ml-auto inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                onClick={() => {
                  void createSlide();
                }}
              >
                <Upload size={14} />
                {isCreating ? t("heroBlock.actions.creating") : t("heroBlock.actions.createSlide")}
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-3">
          {slides.length === 0 ? (
            <div className="rounded-xl border p-5 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              {t("heroBlock.states.empty")}
            </div>
          ) : null}
          {slides.map((item) => {
            const draft = getDraft(item);
            const isBusy = activeSlideActionId === item.id;
            return (
              <article key={item.id} className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <div className="grid gap-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <ImagePreview imageUrl={item.desktop_image_url} label={t("heroBlock.fields.desktopImage")} />
                    <ImagePreview imageUrl={item.mobile_image_url} label={t("heroBlock.fields.mobileImage")} />
                  </div>

                  <LocaleFields
                    titleLabel={t("heroBlock.fields.title")}
                    subtitleLabel={t("heroBlock.fields.subtitle")}
                    form={draft}
                    onChange={(updater) => {
                      setDrafts((prev) => ({ ...prev, [item.id]: updater(getDraft(item)) }));
                    }}
                  />

                  <div className="grid gap-3 lg:grid-cols-3">
                    <TextField
                      label={t("heroBlock.fields.link")}
                      wrapperClassName="grid-rows-[1.1rem_2.25rem]"
                      labelClassName="whitespace-nowrap overflow-hidden text-ellipsis"
                      value={draft.cta_url}
                      onChange={(next) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), cta_url: next } }));
                      }}
                    />
                    <FileField
                      label={t("heroBlock.fields.desktopImage")}
                      wrapperClassName="grid-rows-[1.1rem_2.25rem_auto]"
                      labelClassName="whitespace-nowrap overflow-hidden text-ellipsis"
                      currentImageUrl={item.desktop_image_url}
                      selectedFile={draft.desktop_image_file}
                      onChange={(file) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), desktop_image_file: file } }));
                      }}
                    />
                    <FileField
                      label={t("heroBlock.fields.mobileImage")}
                      wrapperClassName="grid-rows-[1.1rem_2.25rem_auto]"
                      labelClassName="whitespace-nowrap overflow-hidden text-ellipsis"
                      currentImageUrl={item.mobile_image_url}
                      selectedFile={draft.mobile_image_file}
                      onChange={(file) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), mobile_image_file: file } }));
                      }}
                    />
                  </div>

                  <div className="flex flex-wrap items-end gap-3">
                    <ToggleField
                      label={t("heroBlock.fields.active")}
                      widthClassName="w-[118px]"
                      value={draft.is_active}
                      onToggle={() => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), is_active: !getDraft(item).is_active } }));
                      }}
                      yesLabel={t("yes")}
                      noLabel={t("no")}
                    />
                    <NumberStepper
                      label={t("heroBlock.fields.sortOrder")}
                      value={draft.sort_order}
                      min={1}
                      max={999}
                      onChange={(next) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), sort_order: next } }));
                      }}
                    />
                    <button
                      type="button"
                      disabled={isBusy}
                      className="ml-auto inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        void saveSlide(item);
                      }}
                    >
                      <Save size={14} />
                      {t("heroBlock.actions.saveSlide")}
                    </button>
                    <button
                      type="button"
                      disabled={isBusy}
                      className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      onClick={() => {
                        void removeSlide(item);
                      }}
                    >
                      <Trash2 size={14} />
                      {t("heroBlock.actions.deleteSlide")}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </AsyncState>
  );
}
