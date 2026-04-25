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
} from "lucide-react";

import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { getRawMetaString } from "@/features/backoffice/components/orders/nova-poshta-senders.helpers";
import type { BackofficeNovaPoshtaSenderProfile } from "@/features/backoffice/types/nova-poshta.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function NovaPoshtaSendersList({
  rows,
  isLoading,
  error,
  settingPrimaryId,
  deletingId,
  t,
  onCreate,
  onEdit,
  onSetPrimary,
  onDelete,
}: {
  rows: BackofficeNovaPoshtaSenderProfile[];
  isLoading: boolean;
  error: string | null;
  settingPrimaryId: string | null;
  deletingId: string | null;
  t: Translator;
  onCreate: () => void;
  onEdit: (item: BackofficeNovaPoshtaSenderProfile) => void;
  onSetPrimary: (senderId: string) => void;
  onDelete: (item: BackofficeNovaPoshtaSenderProfile) => void;
}) {
  return (
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
            onClick={onCreate}
          >
            <Plus className="h-4 w-4" />
            {t("orders.modals.waybill.settings.actions.create")}
          </button>
        </div>

        <AsyncState isLoading={isLoading} error={error} empty={!rows.length} emptyLabel={t("orders.modals.waybill.settings.empty")}>
          <div className="grid gap-2">
            {rows.map((item) => (
              <NovaPoshtaSenderCard
                key={item.id}
                item={item}
                settingPrimaryId={settingPrimaryId}
                deletingId={deletingId}
                t={t}
                onEdit={onEdit}
                onSetPrimary={onSetPrimary}
                onDelete={onDelete}
              />
            ))}
          </div>
        </AsyncState>
      </div>
    </div>
  );
}

function NovaPoshtaSenderCard({
  item,
  settingPrimaryId,
  deletingId,
  t,
  onEdit,
  onSetPrimary,
  onDelete,
}: {
  item: BackofficeNovaPoshtaSenderProfile;
  settingPrimaryId: string | null;
  deletingId: string | null;
  t: Translator;
  onEdit: (item: BackofficeNovaPoshtaSenderProfile) => void;
  onSetPrimary: (senderId: string) => void;
  onDelete: (item: BackofficeNovaPoshtaSenderProfile) => void;
}) {
  const rawMeta = item.raw_meta && typeof item.raw_meta === "object" ? item.raw_meta : {};
  const counterpartyLabel = getRawMetaString(rawMeta, "counterparty_label");
  const cityLabel = getRawMetaString(rawMeta, "city_label");
  const addressLabel = getRawMetaString(rawMeta, "address_label");
  const counterpartyDisplay = counterpartyLabel || "Не выбран";
  const cityDisplay = cityLabel || "Не выбран";
  const addressDisplay = addressLabel || "Не выбран";

  return (
    <article className="rounded-lg border p-2.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
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
            onClick={() => onSetPrimary(item.id)}
            aria-label={t("orders.modals.waybill.settings.form.default")}
          >
            <Star className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            onClick={() => onEdit(item)}
            aria-label={t("orders.modals.waybill.settings.actions.edit")}
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "#ef4444", backgroundColor: "rgba(239,68,68,.1)", color: "#b91c1c" }}
            disabled={deletingId === item.id}
            onClick={() => onDelete(item)}
            aria-label={t("orders.modals.waybill.settings.actions.delete")}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </article>
  );
}
