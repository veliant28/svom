"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Save, Trash2, Upload } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  createBackofficePromoBanner,
  deleteBackofficePromoBanner,
  getBackofficePromoBannerSettings,
  listBackofficePromoBanners,
  updateBackofficePromoBanner,
  updateBackofficePromoBannerSettings,
} from "@/features/backoffice/api/promo-banners-api";
import { PercentStepper } from "@/features/backoffice/components/pricing/percent-stepper";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import type {
  BackofficePromoBanner,
  BackofficePromoBannerEffect,
  BackofficePromoBannerSettings,
} from "@/features/backoffice/types/promo-banners.types";
import { useAuth } from "@/features/auth/hooks/use-auth";
import {
  PROMO_BANNERS_UPDATED_AT_KEY,
  PROMO_BANNERS_UPDATED_EVENT,
} from "@/shared/lib/promo-banners-sync";

type SettingsForm = {
  autoplay_enabled: boolean;
  transition_effect: BackofficePromoBannerEffect;
  transition_interval_seconds: number;
  transition_speed_ms: number;
  max_active_banners: number;
};

type BannerForm = {
  title: string;
  description: string;
  target_url: string;
  sort_order: number;
  is_active: boolean;
  starts_at: string;
  ends_at: string;
  image_file: File | null;
};

const DEFAULT_SETTINGS_FORM: SettingsForm = {
  autoplay_enabled: true,
  transition_effect: "fade",
  transition_interval_seconds: 5,
  transition_speed_ms: 700,
  max_active_banners: 5,
};

const DEFAULT_BANNER_FORM: BannerForm = {
  title: "",
  description: "",
  target_url: "/catalog",
  sort_order: 1,
  is_active: true,
  starts_at: "",
  ends_at: "",
  image_file: null,
};

function toBannerForm(item: BackofficePromoBanner): BannerForm {
  return {
    title: item.title || "",
    description: item.description || "",
    target_url: item.target_url || "",
    sort_order: Number(item.sort_order || 1),
    is_active: Boolean(item.is_active),
    starts_at: toLocalDateTimeInput(item.starts_at),
    ends_at: toLocalDateTimeInput(item.ends_at),
    image_file: null,
  };
}

function toSettingsForm(value: BackofficePromoBannerSettings): SettingsForm {
  return {
    autoplay_enabled: Boolean(value.autoplay_enabled),
    transition_effect: value.transition_effect,
    transition_interval_seconds: Math.max(1, Math.round(Number(value.transition_interval_ms || 4500) / 1000)),
    transition_speed_ms: clampNumber(Number(value.transition_speed_ms || 700), 150, 10000),
    max_active_banners: clampNumber(Number(value.max_active_banners || 5), 1, 10),
  };
}

function clampNumber(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.max(min, Math.min(max, value));
}

function toLocalDateTimeInput(value: string | null): string {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  const hours = String(parsed.getHours()).padStart(2, "0");
  const minutes = String(parsed.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function emitPromoBannersUpdated(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(PROMO_BANNERS_UPDATED_AT_KEY, String(Date.now()));
  window.dispatchEvent(new CustomEvent(PROMO_BANNERS_UPDATED_EVENT));
}

export function PromoBannersPage() {
  const t = useTranslations("backoffice.common");
  const { token } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [activeBannerActionId, setActiveBannerActionId] = useState<string | null>(null);

  const [settings, setSettings] = useState<BackofficePromoBannerSettings | null>(null);
  const [settingsForm, setSettingsForm] = useState<SettingsForm>(DEFAULT_SETTINGS_FORM);
  const [banners, setBanners] = useState<BackofficePromoBanner[]>([]);
  const [drafts, setDrafts] = useState<Record<string, BannerForm>>({});
  const [newBanner, setNewBanner] = useState<BannerForm>(DEFAULT_BANNER_FORM);

  const getDraft = useCallback((item: BackofficePromoBanner): BannerForm => {
    return drafts[item.id] ?? toBannerForm(item);
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
        getBackofficePromoBannerSettings(token),
        listBackofficePromoBanners(token),
      ]);
      setSettings(nextSettings);
      setSettingsForm(toSettingsForm(nextSettings));
      setBanners(listPayload.results || []);
      setDrafts({});
    } catch (error: unknown) {
      setLoadError(showApiError(error, t("promoBanners.messages.loadFailed")));
    } finally {
      setIsLoading(false);
    }
  }, [showApiError, t, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const canCreate = banners.length < 10;
  const settingsDirty = useMemo(() => {
    if (!settings) {
      return false;
    }
    return (
      settings.autoplay_enabled !== settingsForm.autoplay_enabled
      || settings.transition_effect !== settingsForm.transition_effect
      || Math.round(settings.transition_interval_ms / 1000) !== settingsForm.transition_interval_seconds
      || settings.transition_speed_ms !== settingsForm.transition_speed_ms
      || settings.max_active_banners !== settingsForm.max_active_banners
    );
  }, [settings, settingsForm]);

  async function saveSettings() {
    if (!token) {
      return;
    }
    setIsSavingSettings(true);
    try {
      const payload = await updateBackofficePromoBannerSettings(token, {
        autoplay_enabled: settingsForm.autoplay_enabled,
        transition_effect: settingsForm.transition_effect,
        transition_interval_ms: clampNumber(settingsForm.transition_interval_seconds, 1, 60) * 1000,
        transition_speed_ms: clampNumber(settingsForm.transition_speed_ms, 150, 10000),
        max_active_banners: clampNumber(settingsForm.max_active_banners, 1, 10),
      });
      setSettings(payload);
      setSettingsForm(toSettingsForm(payload));
      showSuccess(t("promoBanners.messages.settingsSaved"));
      emitPromoBannersUpdated();
    } catch (error: unknown) {
      showApiError(error, t("promoBanners.messages.settingsSaveFailed"));
    } finally {
      setIsSavingSettings(false);
    }
  }

  async function saveBanner(item: BackofficePromoBanner) {
    if (!token) {
      return;
    }
    const draft = getDraft(item);
    setActiveBannerActionId(item.id);
    try {
      const updated = await updateBackofficePromoBanner(token, item.id, {
        title: draft.title,
        description: draft.description,
        target_url: draft.target_url,
        sort_order: clampNumber(draft.sort_order, 1, 999),
        is_active: draft.is_active,
        starts_at: draft.starts_at || null,
        ends_at: draft.ends_at || null,
        image: draft.image_file || undefined,
      });
      setBanners((prev) => prev.map((entry) => (entry.id === item.id ? updated : entry)));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      showSuccess(t("promoBanners.messages.bannerSaved"));
      emitPromoBannersUpdated();
    } catch (error: unknown) {
      showApiError(error, t("promoBanners.messages.bannerSaveFailed"));
    } finally {
      setActiveBannerActionId(null);
    }
  }

  async function removeBanner(item: BackofficePromoBanner) {
    if (!token) {
      return;
    }
    setActiveBannerActionId(item.id);
    try {
      await deleteBackofficePromoBanner(token, item.id);
      setBanners((prev) => prev.filter((entry) => entry.id !== item.id));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      showSuccess(t("promoBanners.messages.bannerDeleted"));
      emitPromoBannersUpdated();
    } catch (error: unknown) {
      showApiError(error, t("promoBanners.messages.bannerDeleteFailed"));
    } finally {
      setActiveBannerActionId(null);
    }
  }

  async function createBanner() {
    if (!token || !canCreate || !newBanner.image_file) {
      return;
    }
    setIsCreating(true);
    try {
      const created = await createBackofficePromoBanner(token, {
        title: newBanner.title.trim(),
        description: newBanner.description.trim(),
        target_url: newBanner.target_url.trim(),
        sort_order: clampNumber(newBanner.sort_order, 1, 999),
        is_active: newBanner.is_active,
        starts_at: newBanner.starts_at || null,
        ends_at: newBanner.ends_at || null,
        image: newBanner.image_file,
      });
      setBanners((prev) => [...prev, created].sort((left, right) => left.sort_order - right.sort_order));
      setNewBanner({
        ...DEFAULT_BANNER_FORM,
        sort_order: clampNumber(created.sort_order + 1, 1, 999),
      });
      showSuccess(t("promoBanners.messages.bannerCreated"));
      emitPromoBannersUpdated();
    } catch (error: unknown) {
      showApiError(error, t("promoBanners.messages.bannerCreateFailed"));
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <AsyncState isLoading={isLoading} error={loadError} empty={false} emptyLabel="">
      <section className="grid gap-4">
        <PageHeader
          title={t("promoBanners.title")}
          description={t("promoBanners.subtitle")}
          actions={(
            <button
              type="button"
              className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              onClick={() => {
                void load();
              }}
            >
              {t("promoBanners.actions.refresh")}
            </button>
          )}
        />

        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">{t("promoBanners.settings.title")}</h2>
            <span className="text-xs" style={{ color: "var(--muted)" }}>
              {t("promoBanners.settings.limitLabel", { count: banners.length, max: 10 })}
            </span>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <label className="grid min-w-[220px] gap-1">
              <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                {t("promoBanners.settings.effect")}
              </span>
              <select
                value={settingsForm.transition_effect}
                onChange={(event) => {
                  setSettingsForm((prev) => ({ ...prev, transition_effect: event.target.value as BackofficePromoBannerEffect }));
                }}
                className="h-9 rounded-md border px-2 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              >
                <option value="fade">{t("promoBanners.effects.fade")}</option>
                <option value="slide_left">{t("promoBanners.effects.slideLeft")}</option>
                <option value="slide_up">{t("promoBanners.effects.slideUp")}</option>
                <option value="blinds_vertical">{t("promoBanners.effects.blindsVertical")}</option>
                <option value="zoom_in">{t("promoBanners.effects.zoomIn")}</option>
              </select>
            </label>

            <NumberStepper
              label={t("promoBanners.settings.intervalSeconds")}
              value={settingsForm.transition_interval_seconds}
              min={1}
              max={60}
              onChange={(next) => {
                setSettingsForm((prev) => ({ ...prev, transition_interval_seconds: next }));
              }}
            />

            <NumberStepper
              label={t("promoBanners.settings.speedMs")}
              value={settingsForm.transition_speed_ms}
              min={150}
              max={10000}
              step={50}
              onChange={(next) => {
                setSettingsForm((prev) => ({ ...prev, transition_speed_ms: next }));
              }}
            />

            <NumberStepper
              label={t("promoBanners.settings.maxActive")}
              value={settingsForm.max_active_banners}
              min={1}
              max={10}
              onChange={(next) => {
                setSettingsForm((prev) => ({ ...prev, max_active_banners: next }));
              }}
            />

            <div className="ml-auto flex flex-wrap items-end gap-3">
              <label className="grid w-[118px] gap-1">
                <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                  {t("promoBanners.settings.autoplay")}
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
              {isSavingSettings ? t("promoBanners.actions.saving") : t("promoBanners.actions.saveSettings")}
            </button>
          </div>
        </div>
        </div>

        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          <h2 className="text-sm font-semibold">{t("promoBanners.create.title")}</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
            {t("promoBanners.create.subtitle")} {t("promoBanners.create.imageHint")}
          </p>

          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(260px,1.3fr)_auto_auto_auto]">
            <div className="xl:col-start-1 xl:row-start-1">
              <TextField
                label={t("promoBanners.fields.title")}
                value={newBanner.title}
                onChange={(next) => {
                  setNewBanner((prev) => ({ ...prev, title: next }));
                }}
              />
            </div>

            <div className="xl:col-start-1 xl:row-start-2">
              <TextField
                label={t("promoBanners.fields.description")}
                value={newBanner.description}
                onChange={(next) => {
                  setNewBanner((prev) => ({ ...prev, description: next }));
                }}
              />
            </div>

            <div className="xl:col-start-2 xl:row-start-1">
              <TextField
                label={t("promoBanners.fields.link")}
                value={newBanner.target_url}
                onChange={(next) => {
                  setNewBanner((prev) => ({ ...prev, target_url: next }));
                }}
              />
            </div>

            <label className="grid gap-1 xl:col-start-2 xl:row-start-2">
              <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                {t("promoBanners.fields.image")}
              </span>
              <input
                type="file"
                accept="image/*"
                className="h-9 rounded-md border px-2 text-xs leading-9 file:mr-2 file:h-7 file:rounded file:border-0 file:px-2 file:text-xs file:leading-7"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", lineHeight: "2.25rem" }}
                onChange={(event) => {
                  setNewBanner((prev) => ({ ...prev, image_file: event.target.files?.[0] || null }));
                }}
              />
            </label>

            <div className="xl:col-start-4 xl:row-start-1">
              <NumberStepper
                label={t("promoBanners.fields.sortOrder")}
                value={newBanner.sort_order}
                min={1}
                max={999}
                onChange={(next) => {
                  setNewBanner((prev) => ({ ...prev, sort_order: next }));
                }}
              />
            </div>

            <div className="xl:col-start-3 xl:row-start-1">
              <DateTimeField
                label={t("promoBanners.fields.startsAt")}
                value={newBanner.starts_at}
                onChange={(next) => {
                  setNewBanner((prev) => ({ ...prev, starts_at: next }));
                }}
              />
            </div>

            <div className="xl:col-start-3 xl:row-start-2">
              <DateTimeField
                label={t("promoBanners.fields.endsAt")}
                value={newBanner.ends_at}
                onChange={(next) => {
                  setNewBanner((prev) => ({ ...prev, ends_at: next }));
                }}
              />
            </div>

            <label className="grid w-[118px] gap-1 xl:col-start-5 xl:row-start-1">
              <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                {t("promoBanners.fields.active")}
              </span>
              <button
                type="button"
                className="h-9 rounded-md border px-3 text-sm font-semibold"
                style={{
                  borderColor: newBanner.is_active ? "var(--text)" : "var(--border)",
                  backgroundColor: newBanner.is_active ? "var(--text)" : "var(--surface)",
                  color: newBanner.is_active ? "var(--surface)" : "var(--text)",
                }}
                onClick={() => {
                  setNewBanner((prev) => ({ ...prev, is_active: !prev.is_active }));
                }}
              >
                {newBanner.is_active ? t("yes") : t("no")}
              </button>
            </label>

            <div className="grid w-fit gap-1 md:col-span-2 xl:col-span-1 xl:col-start-5 xl:row-start-2 xl:justify-self-end">
              <span className="text-xs font-semibold uppercase tracking-[0.08em] opacity-0 select-none" aria-hidden="true">
                _
              </span>
              <button
                type="button"
                disabled={!canCreate || isCreating || !newBanner.image_file || !newBanner.title.trim()}
                className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                onClick={() => {
                  void createBanner();
                }}
              >
                <Upload size={14} />
                {isCreating ? t("promoBanners.actions.creating") : t("promoBanners.actions.createBanner")}
              </button>
            </div>
          </div>

        </div>

        <div className="grid gap-3">
          {banners.length === 0 ? (
            <div className="rounded-xl border p-5 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
              {t("promoBanners.states.empty")}
            </div>
          ) : null}
          {banners.map((item) => {
            const draft = getDraft(item);
            const isBusy = activeBannerActionId === item.id;
            return (
              <article key={item.id} className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                <div className="grid gap-3 xl:grid-cols-[240px_minmax(0,1fr)]">
                  <div
                    className="min-h-[120px] rounded-lg border bg-cover bg-center"
                    style={{ borderColor: "var(--border)", backgroundImage: `url(${item.image_url})` }}
                  />
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(260px,1.3fr)_minmax(0,1fr)_minmax(0,1fr)]">
                    <TextField
                      label={t("promoBanners.fields.title")}
                      value={draft.title}
                      onChange={(next) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), title: next } }));
                      }}
                    />
                    <TextField
                      label={t("promoBanners.fields.link")}
                      value={draft.target_url}
                      onChange={(next) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), target_url: next } }));
                      }}
                    />
                    <DateTimeField
                      label={t("promoBanners.fields.startsAt")}
                      value={draft.starts_at}
                      onChange={(next) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), starts_at: next } }));
                      }}
                    />
                    <NumberStepper
                      label={t("promoBanners.fields.sortOrder")}
                      value={draft.sort_order}
                      min={1}
                      max={999}
                      onChange={(next) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), sort_order: next } }));
                      }}
                    />
                    <TextField
                      label={t("promoBanners.fields.description")}
                      value={draft.description}
                      onChange={(next) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), description: next } }));
                      }}
                    />
                    <label className="grid gap-1">
                      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                        {t("promoBanners.fields.image")}
                      </span>
                      <input
                        type="file"
                        accept="image/*"
                        className="h-9 rounded-md border px-2 text-xs leading-9 file:mr-2 file:h-7 file:rounded file:border-0 file:px-2 file:text-xs file:leading-7"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", lineHeight: "2.25rem" }}
                        onChange={(event) => {
                          setDrafts((prev) => ({
                            ...prev,
                            [item.id]: { ...getDraft(item), image_file: event.target.files?.[0] || null },
                          }));
                        }}
                      />
                    </label>
                    <DateTimeField
                      label={t("promoBanners.fields.endsAt")}
                      value={draft.ends_at}
                      onChange={(next) => {
                        setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), ends_at: next } }));
                      }}
                    />
                    <label className="grid w-[118px] gap-1">
                      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                        {t("promoBanners.fields.active")}
                      </span>
                      <button
                        type="button"
                        className="h-9 rounded-md border px-3 text-sm font-semibold"
                        style={{
                          borderColor: draft.is_active ? "var(--text)" : "var(--border)",
                          backgroundColor: draft.is_active ? "var(--text)" : "var(--surface)",
                          color: draft.is_active ? "var(--surface)" : "var(--text)",
                        }}
                        onClick={() => {
                          setDrafts((prev) => ({ ...prev, [item.id]: { ...getDraft(item), is_active: !getDraft(item).is_active } }));
                        }}
                      >
                        {draft.is_active ? t("yes") : t("no")}
                      </button>
                    </label>
                  </div>
                </div>

                <div className="mt-3 flex justify-end gap-2">
                  <button
                    type="button"
                    disabled={isBusy}
                    className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                    style={{ borderColor: "#2563eb", backgroundColor: "#2563eb", color: "#fff" }}
                    onClick={() => {
                      void saveBanner(item);
                    }}
                  >
                    <Save size={14} />
                    {t("promoBanners.actions.saveBanner")}
                  </button>
                  <button
                    type="button"
                    disabled={isBusy}
                    className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
                    style={{ borderColor: "#dc2626", backgroundColor: "#dc2626", color: "#fff" }}
                    onClick={() => {
                      void removeBanner(item);
                    }}
                  >
                    <Trash2 size={14} />
                    {t("promoBanners.actions.deleteBanner")}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </AsyncState>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (next: string) => void }) {
  return (
    <label className="grid gap-1">
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <input
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="h-9 rounded-md border px-2 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      />
    </label>
  );
}

function DateTimeField({ label, value, onChange }: { label: string; value: string; onChange: (next: string) => void }) {
  return (
    <label className="grid w-[188px] gap-1">
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <input
        type="datetime-local"
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="h-9 rounded-md border px-2 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      />
    </label>
  );
}

function NumberStepper({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (next: number) => void;
  min: number;
  max: number;
  step?: number;
}) {
  const safeValue = clampNumber(value, min, max);
  return (
    <label className="grid w-fit gap-1 justify-items-start">
      <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <PercentStepper
        value={safeValue}
        onChange={onChange}
        min={min}
        max={max}
        step={step}
        minusLabel={`${label} -`}
        plusLabel={`${label} +`}
        inputLabel={label}
        suffix=""
        inputMode="numeric"
        integerOnly
        containerClassName="w-fit"
      />
    </label>
  );
}
