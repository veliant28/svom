"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { ShortToggle } from "@/features/backoffice/components/widgets/short-toggle";
import { useFooterSettings } from "@/features/backoffice/hooks/use-footer-settings";
import {
  type FooterPhoneFormat,
  formatFooterPhoneForInput,
  formatFooterPhoneForSave,
  normalizeFooterPhoneDigits,
} from "@/shared/lib/footer-phone";

type WeekdayCode = "ПН" | "ВТ" | "СР" | "ЧТ" | "ПТ" | "СБ" | "ВС";

const WEEKDAY_CODES: WeekdayCode[] = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"];
const DEFAULT_SELECTED_DAYS: WeekdayCode[] = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ"];
const DEFAULT_START_TIME = "10:00";
const DEFAULT_END_TIME = "17:00";

type FooterForm = {
  selectedDays: WeekdayCode[];
  startTime: string;
  endTime: string;
  phoneFormat: FooterPhoneFormat;
  mobilePhoneDigits: string;
  tollFreePhoneDigits: string;
};

const EMPTY_FORM: FooterForm = {
  selectedDays: DEFAULT_SELECTED_DAYS,
  startTime: DEFAULT_START_TIME,
  endTime: DEFAULT_END_TIME,
  phoneFormat: "mobile",
  mobilePhoneDigits: "",
  tollFreePhoneDigits: "",
};

export function FooterSettingsPage() {
  const t = useTranslations("backoffice.common");
  const { settings, isLoading, isSaving, save } = useFooterSettings({ t });
  const [form, setForm] = useState<FooterForm>(EMPTY_FORM);
  const [isClientMounted, setIsClientMounted] = useState(false);

  useEffect(() => {
    setIsClientMounted(true);
  }, []);

  useEffect(() => {
    if (!settings) {
      return;
    }
    const parsedWorkingHours = parseWorkingHours(settings.working_hours || "");
    const resolvedFormat: FooterPhoneFormat = settings.phone_format === "toll_free_0800" ? "toll_free_0800" : "mobile";
    const normalizedFromSettings = normalizeFooterPhoneDigits(settings.phone || "", resolvedFormat);
    setForm({
      selectedDays: parsedWorkingHours.selectedDays,
      startTime: parsedWorkingHours.startTime,
      endTime: parsedWorkingHours.endTime,
      phoneFormat: resolvedFormat,
      mobilePhoneDigits: resolvedFormat === "mobile" ? normalizedFromSettings : "",
      tollFreePhoneDigits: resolvedFormat === "toll_free_0800" ? normalizedFromSettings : "",
    });
  }, [settings]);

  const dayLabelByCode: Record<WeekdayCode, string> = {
    ПН: t("footerSettings.days.mon"),
    ВТ: t("footerSettings.days.tue"),
    СР: t("footerSettings.days.wed"),
    ЧТ: t("footerSettings.days.thu"),
    ПТ: t("footerSettings.days.fri"),
    СБ: t("footerSettings.days.sat"),
    ВС: t("footerSettings.days.sun"),
  };

  const activePhoneDigits = form.phoneFormat === "mobile" ? form.mobilePhoneDigits : form.tollFreePhoneDigits;
  const serializedWorkingHours = useMemo(
    () => buildWorkingHours(form.selectedDays, form.startTime, form.endTime),
    [form.endTime, form.selectedDays, form.startTime],
  );
  const serializedPhone = useMemo(
    () => formatFooterPhoneForSave(activePhoneDigits, form.phoneFormat),
    [activePhoneDigits, form.phoneFormat],
  );
  const maskedPhone = useMemo(
    () => formatFooterPhoneForInput(activePhoneDigits, form.phoneFormat),
    [activePhoneDigits, form.phoneFormat],
  );
  const initialPhoneFormat = useMemo(() => settings?.phone_format || "mobile", [settings?.phone_format]);
  const initialMobilePhoneDigits = useMemo(
    () => (initialPhoneFormat === "mobile" ? normalizeFooterPhoneDigits(settings?.phone || "", "mobile") : ""),
    [initialPhoneFormat, settings?.phone],
  );
  const initialTollFreePhoneDigits = useMemo(
    () => (initialPhoneFormat === "toll_free_0800" ? normalizeFooterPhoneDigits(settings?.phone || "", "toll_free_0800") : ""),
    [initialPhoneFormat, settings?.phone],
  );
  const isDirty = (settings?.working_hours || "").trim() !== serializedWorkingHours
    || initialMobilePhoneDigits !== form.mobilePhoneDigits
    || initialTollFreePhoneDigits !== form.tollFreePhoneDigits
    || initialPhoneFormat !== form.phoneFormat;
  const isWorkingHoursValid = form.selectedDays.length > 0 && isValidTime(form.startTime) && isValidTime(form.endTime);
  const isPhoneValid = form.phoneFormat === "mobile"
    ? form.mobilePhoneDigits.length === 10
    : form.tollFreePhoneDigits.length === 10 && form.tollFreePhoneDigits.startsWith("0800");
  const isFormBusy = isLoading || isSaving;
  const inputDisabled = isClientMounted ? isFormBusy : undefined;
  const saveDisabled = isClientMounted ? isFormBusy || !isDirty || !isWorkingHoursValid || !isPhoneValid : undefined;

  return (
    <section className="grid gap-4">
      <PageHeader title={t("footerSettings.title")} description={t("footerSettings.subtitle")} />

      <div
        className="grid gap-4 rounded-xl border p-4 md:p-5"
        style={{
          borderColor: "var(--border)",
          backgroundColor: "var(--surface)",
        }}
      >
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_170px_320px_auto]">
          <div className="grid min-w-0 flex-1 grid-rows-[16px_40px]">
            <span className="text-xs font-semibold uppercase leading-none tracking-[0.08em]" style={{ color: "var(--muted)" }}>
              {t("footerSettings.fields.workingHours")}
            </span>
            <div className="mt-1 flex h-10 flex-wrap items-center gap-2 xl:flex-nowrap">
              {WEEKDAY_CODES.map((code) => {
                const isActive = form.selectedDays.includes(code);
                const isWeekend = code === "СБ" || code === "ВС";
                const activeColor = isWeekend ? "#ea580c" : "#2563eb";
                return (
                  <button
                    key={code}
                    type="button"
                    disabled={inputDisabled}
                    className="inline-flex h-10 items-center rounded-md border px-3 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                    style={{
                      borderColor: isActive ? activeColor : "var(--border)",
                      backgroundColor: isActive ? activeColor : "var(--surface-2)",
                      color: isActive ? "#ffffff" : "var(--text)",
                    }}
                    onClick={() => {
                      setForm((prev) => ({
                        ...prev,
                        selectedDays: prev.selectedDays.includes(code)
                          ? prev.selectedDays.filter((item) => item !== code)
                          : WEEKDAY_CODES.filter((item) => item === code || prev.selectedDays.includes(item)),
                      }));
                    }}
                  >
                    {dayLabelByCode[code]}
                  </button>
                );
              })}
              <div className="ml-0 inline-flex items-center gap-2 whitespace-nowrap xl:ml-1">
                <span className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                  {t("footerSettings.fields.timeFrom")}
                </span>
                <input
                  type="time"
                  step={60}
                  className="h-10 rounded-md border px-2 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  value={form.startTime}
                  onChange={(event) => {
                    setForm((prev) => ({ ...prev, startTime: event.target.value }));
                  }}
                  disabled={inputDisabled}
                />
                <span className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
                  {t("footerSettings.fields.timeTo")}
                </span>
                <input
                  type="time"
                  step={60}
                  className="h-10 rounded-md border px-2 text-sm"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                  value={form.endTime}
                  onChange={(event) => {
                    setForm((prev) => ({ ...prev, endTime: event.target.value }));
                  }}
                  disabled={inputDisabled}
                />
              </div>
            </div>
          </div>

          <div className="grid w-full grid-rows-[16px_40px] justify-items-center sm:w-[170px] xl:w-[170px]">
            <span className="text-center text-xs font-semibold uppercase leading-none tracking-[0.08em]" style={{ color: "var(--muted)" }}>
              {t("footerSettings.fields.phoneFormat")}
            </span>
            <div className="mt-1 flex h-10 w-full items-center justify-center">
              <ShortToggle
                value={form.phoneFormat}
                ariaLabel={t("footerSettings.fields.phoneFormat")}
                className="justify-center"
                disabled={inputDisabled}
                options={[
                  { value: "mobile", label: t("footerSettings.phoneFormats.mobile"), activeColor: "#2563eb" },
                  { value: "toll_free_0800", label: t("footerSettings.phoneFormats.tollFree"), activeColor: "#2563eb" },
                ]}
                onChange={(nextFormat) => {
                  setForm((prev) => ({
                    ...prev,
                    phoneFormat: nextFormat,
                  }));
                }}
              />
            </div>
          </div>

          <div className="grid w-full grid-rows-[16px_40px] sm:w-[320px] xl:w-[320px]">
            <span className="text-xs font-semibold uppercase leading-none tracking-[0.08em]" style={{ color: "var(--muted)" }}>
              {t("footerSettings.fields.phone")}
            </span>
            <div className="mt-1 flex h-10 items-center">
              <input
                className="h-10 w-full rounded-md border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                inputMode="numeric"
                autoComplete="tel-national"
                value={maskedPhone}
                onChange={(event) => {
                  setForm((prev) => {
                    const previousDigits = prev.phoneFormat === "mobile" ? prev.mobilePhoneDigits : prev.tollFreePhoneDigits;
                    const previousMasked = formatFooterPhoneForInput(previousDigits, prev.phoneFormat);
                    let nextDigits = normalizeFooterPhoneDigits(event.target.value, prev.phoneFormat);
                    const removedOnlyMaskChar =
                      nextDigits === previousDigits && event.target.value.length < previousMasked.length;
                    if (removedOnlyMaskChar) {
                      nextDigits = previousDigits.slice(0, -1);
                    }
                    if (prev.phoneFormat === "mobile") {
                      return { ...prev, mobilePhoneDigits: nextDigits };
                    }
                    return { ...prev, tollFreePhoneDigits: nextDigits };
                  });
                }}
                disabled={inputDisabled}
                placeholder={form.phoneFormat === "mobile" ? t("footerSettings.placeholders.phone") : t("footerSettings.placeholders.phoneTollFree")}
              />
            </div>
          </div>

          <div className="grid w-full grid-rows-[16px_40px] sm:w-auto xl:justify-self-end">
            <span className="invisible text-xs font-semibold uppercase leading-none tracking-[0.08em]">
              .
            </span>
            <div className="mt-1 flex h-10 items-center">
              <button
                type="button"
                className="h-10 w-full rounded-md border px-4 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60 md:w-auto"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                disabled={saveDisabled}
                onClick={() => {
                  void save({
                    working_hours: serializedWorkingHours,
                    phone_format: form.phoneFormat,
                    phone: serializedPhone,
                  });
                }}
              >
                {isSaving ? t("footerSettings.actions.saving") : t("footerSettings.actions.save")}
              </button>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-xs" style={{ color: "#b45309" }}>
            {!form.selectedDays.length
              ? t("footerSettings.validation.daysRequired")
              : !isPhoneValid
                ? form.phoneFormat === "mobile"
                  ? t("footerSettings.validation.phoneIncomplete")
                  : t("footerSettings.validation.phoneIncompleteTollFree")
                : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function isValidTime(value: string): boolean {
  return /^([01]\d|2[0-3]):[0-5]\d$/.test(value);
}

function normalizeTime(value: string, fallback: string): string {
  const match = /^(\d{1,2}):(\d{2})$/.exec(String(value || "").trim());
  if (!match) {
    return fallback;
  }
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (Number.isNaN(hours) || Number.isNaN(minutes) || hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
    return fallback;
  }
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function parseWorkingHours(value: string): Pick<FooterForm, "selectedDays" | "startTime" | "endTime"> {
  const normalized = String(value || "").toUpperCase();
  const selectedDays = WEEKDAY_CODES.filter((code) => normalized.includes(code));
  const resolvedDays = selectedDays.length ? selectedDays : DEFAULT_SELECTED_DAYS;
  const timeMatch = normalized.match(/(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})/);
  const startTime = normalizeTime(timeMatch?.[1] || "", DEFAULT_START_TIME);
  const endTime = normalizeTime(timeMatch?.[2] || "", DEFAULT_END_TIME);
  return {
    selectedDays: resolvedDays,
    startTime,
    endTime,
  };
}

function buildWorkingHours(selectedDays: WeekdayCode[], startTime: string, endTime: string): string {
  const days = (selectedDays.length ? selectedDays : DEFAULT_SELECTED_DAYS).join(", ");
  return `${days} ${normalizeTime(startTime, DEFAULT_START_TIME)}-${normalizeTime(endTime, DEFAULT_END_TIME)}`;
}
