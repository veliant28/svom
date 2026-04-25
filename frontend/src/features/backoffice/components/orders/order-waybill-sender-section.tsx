import { MoreHorizontal } from "lucide-react";
import type { Dispatch, RefObject, SetStateAction } from "react";

import type { Translator } from "@/features/backoffice/components/orders/order-waybill-modal.helpers";
import { resolveSenderDisplayName } from "@/features/backoffice/components/orders/order-waybill-party.helpers";
import type { WaybillFormPayload } from "@/features/backoffice/lib/orders/waybill-form";
import type { BackofficeNovaPoshtaSenderProfile } from "@/features/backoffice/types/nova-poshta.types";

export function OrderWaybillSenderSection({
  senderMenuRef,
  senderMenuOpen,
  senderProfiles,
  sender,
  senderCounterpartyDisplay,
  senderCityDisplay,
  senderAddressDisplay,
  formDisabled,
  t,
  setSenderMenuOpen,
  setPayload,
}: {
  senderMenuRef: RefObject<HTMLDivElement | null>;
  senderMenuOpen: boolean;
  senderProfiles: BackofficeNovaPoshtaSenderProfile[];
  sender: BackofficeNovaPoshtaSenderProfile | undefined;
  senderCounterpartyDisplay: string;
  senderCityDisplay: string;
  senderAddressDisplay: string;
  formDisabled: boolean;
  t: Translator;
  setSenderMenuOpen: Dispatch<SetStateAction<boolean>>;
  setPayload: Dispatch<SetStateAction<WaybillFormPayload>>;
}) {
  return (
    <section
      className="order-1 rounded-md border p-3 xl:h-[460px] xl:overflow-y-auto"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <div className="flex min-h-8 items-center justify-between gap-2">
        <h3 className="text-foreground text-sm font-semibold">{t("orders.modals.waybill.fields.sender")}</h3>
        <div ref={senderMenuRef} className="relative">
          <button
            type="button"
            className="inline-flex h-8 cursor-pointer items-center justify-center rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
            onClick={() => setSenderMenuOpen((prev) => !prev)}
            disabled={formDisabled || senderProfiles.length === 0}
            aria-label={t("orders.modals.waybill.fields.sender")}
          >
            <MoreHorizontal className="size-4 stroke-[2.5]" />
          </button>
          {senderMenuOpen ? (
            <div
              className="absolute right-0 top-[calc(100%+0.35rem)] z-[100] min-w-64 rounded-md border p-1.5 shadow-lg"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
            >
              <p className="px-2 py-1 text-xs" style={{ color: "var(--muted)" }}>
                {t("orders.modals.waybill.fields.sender")}
              </p>
              <div className="px-2 pb-1 text-sm font-medium">{resolveSenderDisplayName(sender)}</div>
              <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
              {senderProfiles.length === 0 ? (
                <p className="px-2 py-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("orders.modals.waybill.settings.empty")}
                </p>
              ) : (
                <div className="grid gap-0.5">
                  {senderProfiles.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100/70 dark:hover:bg-slate-700/40"
                      onClick={() => {
                        setPayload((prev) => ({ ...prev, sender_profile_id: item.id }));
                        setSenderMenuOpen(false);
                      }}
                    >
                      <span className="block">{resolveSenderDisplayName(item)}</span>
                      {item.is_default ? (
                        <span className="block text-xs" style={{ color: "var(--muted)" }}>
                          {t("orders.modals.waybill.settings.default")}
                        </span>
                      ) : null}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>

      <div className="grid gap-1 pt-0.5">
        <div className="grid gap-1">
          <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.settings.form.phone")}</span>
          <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <span className={sender?.phone ? "text-[var(--text)]" : "text-[var(--muted)]"}>{sender?.phone || "—"}</span>
          </div>
        </div>

        <div className="grid gap-1">
          <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.fields.counterparty")}</span>
          <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <span className={senderCounterpartyDisplay ? "truncate text-[var(--text)]" : "truncate text-[var(--muted)]"}>
              {senderCounterpartyDisplay || "—"}
            </span>
          </div>
        </div>

        <div className="grid gap-1">
          <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.settings.form.contactName")}</span>
          <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <span className={sender?.contact_name ? "text-[var(--text)]" : "text-[var(--muted)]"}>{sender?.contact_name || "—"}</span>
          </div>
        </div>

        <div className="grid gap-1">
          <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.settings.form.cityRef")}</span>
          <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <span className={senderCityDisplay ? "truncate text-[var(--text)]" : "truncate text-[var(--muted)]"}>
              {senderCityDisplay || "—"}
            </span>
          </div>
        </div>

        <div className="grid gap-1">
          <span className="text-xs" style={{ color: "var(--muted)" }}>{t("orders.modals.waybill.settings.form.addressRef")}</span>
          <div className="flex h-10 items-center rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <span className={senderAddressDisplay ? "truncate text-[var(--text)]" : "truncate text-[var(--muted)]"}>
              {senderAddressDisplay || "—"}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
