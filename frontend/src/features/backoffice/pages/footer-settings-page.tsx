"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useFooterSettings } from "@/features/backoffice/hooks/use-footer-settings";

type WeekdayCode = "ПН" | "ВТ" | "СР" | "ЧТ" | "ПТ" | "СБ" | "ВС";

const WEEKDAY_CODES: WeekdayCode[] = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"];
const DEFAULT_SELECTED_DAYS: WeekdayCode[] = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ"];
const DEFAULT_START_TIME = "10:00";
const DEFAULT_END_TIME = "17:00";

type FooterForm = {
  selectedDays: WeekdayCode[];
  startTime: string;
  endTime: string;
  phoneDigits: string;
};

const EMPTY_FORM: FooterForm = {
  selectedDays: DEFAULT_SELECTED_DAYS,
  startTime: DEFAULT_START_TIME,
  endTime: DEFAULT_END_TIME,
  phoneDigits: "",
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
    setForm({
      selectedDays: parsedWorkingHours.selectedDays,
      startTime: parsedWorkingHours.startTime,
      endTime: parsedWorkingHours.endTime,
      phoneDigits: normalizePhoneDigits(settings.phone || ""),
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

  const serializedWorkingHours = useMemo(
    () => buildWorkingHours(form.selectedDays, form.startTime, form.endTime),
    [form.endTime, form.selectedDays, form.startTime],
  );
  const serializedPhone = useMemo(() => formatPhoneForSave(form.phoneDigits), [form.phoneDigits]);
  const maskedPhone = useMemo(() => formatPhoneForInput(form.phoneDigits), [form.phoneDigits]);
  const initialPhoneDigits = useMemo(() => normalizePhoneDigits(settings?.phone || ""), [settings?.phone]);
  const isDirty = (settings?.working_hours || "").trim() !== serializedWorkingHours || initialPhoneDigits !== form.phoneDigits;
  const isWorkingHoursValid = form.selectedDays.length > 0 && isValidTime(form.startTime) && isValidTime(form.endTime);
  const isPhoneValid = form.phoneDigits.length === 10;
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
        <div className="flex flex-wrap items-end gap-3 xl:flex-nowrap">
          <div className="min-w-0 flex-1">
            <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
              {t("footerSettings.fields.workingHours")}
            </span>
            <div className="mt-1 flex flex-wrap items-center gap-2 xl:flex-nowrap">
              {WEEKDAY_CODES.map((code) => {
                const isActive = form.selectedDays.includes(code);
                const isWeekend = code === "СБ" || code === "ВС";
                const activeColor = isWeekend ? "#ea580c" : "#2563eb";
                return (
                  <button
                    key={code}
                    type="button"
                    disabled={inputDisabled}
                    className="inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60"
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
                  className="h-9 rounded-md border px-2 text-sm"
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
                  className="h-9 rounded-md border px-2 text-sm"
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

          <label className="grid w-full gap-1 sm:w-[320px] xl:w-[320px]">
            <span className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>
              {t("footerSettings.fields.phone")}
            </span>
            <input
              className="h-10 rounded-md border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              inputMode="numeric"
              autoComplete="tel-national"
              value={maskedPhone}
              onChange={(event) => {
                setForm((prev) => {
                  const previousDigits = prev.phoneDigits;
                  const previousMasked = formatPhoneForInput(previousDigits);
                  let nextDigits = normalizePhoneDigits(event.target.value);
                  const removedOnlyMaskChar =
                    nextDigits === previousDigits && event.target.value.length < previousMasked.length;
                  if (removedOnlyMaskChar) {
                    nextDigits = previousDigits.slice(0, -1);
                  }
                  return { ...prev, phoneDigits: nextDigits };
                });
              }}
              disabled={inputDisabled}
              placeholder={t("footerSettings.placeholders.phone")}
            />
          </label>

          <div className="flex w-full sm:w-auto xl:justify-end">
            <button
              type="button"
              className="h-10 w-full rounded-md border px-4 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60 md:w-auto"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              disabled={saveDisabled}
              onClick={() => {
                void save({
                  working_hours: serializedWorkingHours,
                  phone: serializedPhone,
                });
              }}
            >
              {isSaving ? t("footerSettings.actions.saving") : t("footerSettings.actions.save")}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-xs" style={{ color: "#b45309" }}>
            {!form.selectedDays.length
              ? t("footerSettings.validation.daysRequired")
              : !isPhoneValid
                ? t("footerSettings.validation.phoneIncomplete")
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

function normalizePhoneDigits(value: string): string {
  const digits = String(value || "").replace(/\D+/g, "");
  if (!digits) {
    return "";
  }
  if (digits.startsWith("380")) {
    return digits.slice(2, 12);
  }
  if (digits.startsWith("38")) {
    const rest = digits.slice(2);
    if (!rest) {
      return "";
    }
    if (rest.startsWith("0")) {
      return rest.slice(0, 10);
    }
    return `0${rest}`.slice(0, 10);
  }
  if (digits.startsWith("0")) {
    return digits.slice(0, 10);
  }
  if (digits.length >= 10) {
    const tail = digits.slice(-10);
    return tail.startsWith("0") ? tail : `0${tail}`.slice(0, 10);
  }
  return `0${digits}`.slice(0, 10);
}

function formatPhoneForInput(digits: string): string {
  const normalized = normalizePhoneDigits(digits);
  if (!normalized) {
    return "";
  }
  const operator = normalized.slice(0, 3);
  const left = normalized.slice(3, 6);
  const middle = normalized.slice(6, 8);
  const right = normalized.slice(8, 10);
  let value = "38";
  if (operator) {
    value += `(${operator}`;
    if (operator.length === 3) {
      value += ")";
    }
  }
  if (left) {
    value += left;
  }
  if (middle) {
    value += `-${middle}`;
  }
  if (right) {
    value += `-${right}`;
  }
  return value;
}

function formatPhoneForSave(digits: string): string {
  const normalized = normalizePhoneDigits(digits);
  if (!normalized) {
    return "";
  }
  return formatPhoneForInput(normalized);
}
