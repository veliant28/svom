"use client";

import { LoaderCircle } from "lucide-react";

import type { BackofficeGoogleEventSetting } from "@/features/backoffice/api/seo-api.types";

const EVENT_I18N_KEY_BY_NAME: Record<string, { label: string; description: string }> = {
  view_item: {
    label: "seo.google.eventLabels.view_item",
    description: "seo.google.eventDescriptions.view_item",
  },
  add_to_cart: {
    label: "seo.google.eventLabels.add_to_cart",
    description: "seo.google.eventDescriptions.add_to_cart",
  },
  begin_checkout: {
    label: "seo.google.eventLabels.begin_checkout",
    description: "seo.google.eventDescriptions.begin_checkout",
  },
  purchase: {
    label: "seo.google.eventLabels.purchase",
    description: "seo.google.eventDescriptions.purchase",
  },
  refund: {
    label: "seo.google.eventLabels.refund",
    description: "seo.google.eventDescriptions.refund",
  },
  search: {
    label: "seo.google.eventLabels.search",
    description: "seo.google.eventDescriptions.search",
  },
  view_item_list: {
    label: "seo.google.eventLabels.view_item_list",
    description: "seo.google.eventDescriptions.view_item_list",
  },
};

export function GoogleEventsCard({
  events,
  activeEventId,
  canManage,
  onToggle,
  t,
}: {
  events: BackofficeGoogleEventSetting[];
  activeEventId: string | null;
  canManage: boolean;
  onToggle: (eventId: string, enabled: boolean) => Promise<boolean>;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  return (
    <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("seo.google.eventsTitle")}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{t("seo.google.eventsHint")}</p>

      <div className="mt-3 grid gap-2">
        {events.length ? events.map((event) => {
          const isBusy = activeEventId === event.id;
          const i18nKeys = EVENT_I18N_KEY_BY_NAME[event.event_name];
          const label = i18nKeys ? t(i18nKeys.label) : (event.label || event.event_name);
          const description = i18nKeys ? t(i18nKeys.description) : (event.description || event.event_name);
          return (
            <div key={event.id} className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium">{label}</p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>{description}</p>
                </div>
                <button
                  type="button"
                  disabled={!canManage || isBusy}
                  className="inline-flex h-8 items-center gap-2 rounded-md border px-2 text-xs font-semibold disabled:opacity-60"
                  style={{
                    borderColor: event.is_enabled ? "#16a34a" : "var(--border)",
                    backgroundColor: event.is_enabled ? "#16a34a" : "var(--surface)",
                    color: event.is_enabled ? "#fff" : "var(--text)",
                  }}
                  onClick={() => {
                    void onToggle(event.id, !event.is_enabled);
                  }}
                >
                  {isBusy ? <LoaderCircle size={13} className="animate-spin" /> : null}
                  {event.is_enabled ? t("seo.status.enabled") : t("seo.status.disabled")}
                </button>
              </div>
            </div>
          );
        }) : (
          <div className="rounded-lg border px-3 py-5 text-center text-sm" style={{ borderColor: "var(--border)", color: "var(--muted)" }}>
            {t("seo.states.chartEmpty")}
          </div>
        )}
      </div>
    </section>
  );
}
