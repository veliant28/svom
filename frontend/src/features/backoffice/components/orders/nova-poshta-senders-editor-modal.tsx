import { Plus, X } from "lucide-react";
import type { Dispatch, RefObject, SetStateAction } from "react";

import type {
  ModalAddressSuggestion,
  NovaPoshtaSenderFormState,
} from "@/features/backoffice/components/orders/nova-poshta-senders.helpers";
import type {
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaSenderProfile,
} from "@/features/backoffice/types/nova-poshta.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;
type LookupRootRef = RefObject<HTMLDivElement | null>;

export function NovaPoshtaSendersEditorModal({
  editingId,
  rows,
  form,
  saving,
  savingTokenOnly,
  counterpartyLookupRootRef,
  modalCityLookupRootRef,
  modalAddressLookupRootRef,
  counterpartyQuery,
  counterparties,
  counterpartyLoading,
  counterpartyDetailsLoading,
  activeCounterpartyIndex,
  modalCityQuery,
  modalCities,
  modalCityLoading,
  activeModalCityIndex,
  modalAddressQuery,
  modalAddresses,
  modalAddressLoading,
  activeModalAddressIndex,
  selectedModalAddressRef,
  selectedModalAddressLabel,
  t,
  setForm,
  setCounterpartyQuery,
  setCounterparties,
  setActiveCounterpartyIndex,
  setModalCityQuery,
  setModalCities,
  setActiveModalCityIndex,
  setSelectedSettlementRef,
  setModalAddressQuery,
  setModalAddresses,
  setActiveModalAddressIndex,
  setSelectedModalAddressRef,
  setSelectedModalAddressLabel,
  onClose,
  onSubmit,
  onSaveTokenOnly,
  onCounterpartySelect,
  onModalCitySelect,
  onModalAddressSelect,
}: {
  editingId: string | null;
  rows: BackofficeNovaPoshtaSenderProfile[];
  form: NovaPoshtaSenderFormState;
  saving: boolean;
  savingTokenOnly: boolean;
  counterpartyLookupRootRef: LookupRootRef;
  modalCityLookupRootRef: LookupRootRef;
  modalAddressLookupRootRef: LookupRootRef;
  counterpartyQuery: string;
  counterparties: BackofficeNovaPoshtaLookupCounterparty[];
  counterpartyLoading: boolean;
  counterpartyDetailsLoading: boolean;
  activeCounterpartyIndex: number;
  modalCityQuery: string;
  modalCities: BackofficeNovaPoshtaLookupSettlement[];
  modalCityLoading: boolean;
  activeModalCityIndex: number;
  modalAddressQuery: string;
  modalAddresses: ModalAddressSuggestion[];
  modalAddressLoading: boolean;
  activeModalAddressIndex: number;
  selectedModalAddressRef: string;
  selectedModalAddressLabel: string;
  t: Translator;
  setForm: Dispatch<SetStateAction<NovaPoshtaSenderFormState>>;
  setCounterpartyQuery: Dispatch<SetStateAction<string>>;
  setCounterparties: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupCounterparty[]>>;
  setActiveCounterpartyIndex: Dispatch<SetStateAction<number>>;
  setModalCityQuery: Dispatch<SetStateAction<string>>;
  setModalCities: Dispatch<SetStateAction<BackofficeNovaPoshtaLookupSettlement[]>>;
  setActiveModalCityIndex: Dispatch<SetStateAction<number>>;
  setSelectedSettlementRef: Dispatch<SetStateAction<string>>;
  setModalAddressQuery: Dispatch<SetStateAction<string>>;
  setModalAddresses: Dispatch<SetStateAction<ModalAddressSuggestion[]>>;
  setActiveModalAddressIndex: Dispatch<SetStateAction<number>>;
  setSelectedModalAddressRef: Dispatch<SetStateAction<string>>;
  setSelectedModalAddressLabel: Dispatch<SetStateAction<string>>;
  onClose: () => void;
  onSubmit: () => void;
  onSaveTokenOnly: () => void;
  onCounterpartySelect: (row: BackofficeNovaPoshtaLookupCounterparty) => void;
  onModalCitySelect: (row: BackofficeNovaPoshtaLookupSettlement) => void;
  onModalAddressSelect: (row: ModalAddressSuggestion) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button type="button" className="absolute inset-0 bg-black/40" aria-label={t("orders.actions.closeModal")} onClick={onClose} />
      <form
        className="relative z-10 w-full max-w-2xl rounded-xl border p-3"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">
            {editingId ? t("orders.modals.waybill.settings.actions.update") : t("orders.modals.waybill.settings.actions.create")}
          </h3>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
            aria-label={t("orders.actions.closeModal")}
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid gap-2 md:grid-cols-2">
          <div className="md:col-span-2">
            <div className="flex gap-2">
              <input
                className="h-10 min-w-0 flex-1 rounded-md border px-3 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                placeholder={editingId ? `${t("orders.modals.waybill.settings.form.apiToken")} (optional)` : t("orders.modals.waybill.settings.form.apiToken")}
                value={form.api_token}
                onChange={(event) => setForm((prev) => ({ ...prev, api_token: event.target.value }))}
              />
              <button
                type="button"
                className="inline-flex h-10 shrink-0 items-center rounded-md border px-3 text-xs font-semibold"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                onClick={onSaveTokenOnly}
                disabled={savingTokenOnly}
              >
                {savingTokenOnly ? t("loading") : "Сохранить токен"}
              </button>
            </div>
            {editingId ? (
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                Текущий токен: {rows.find((row) => row.id === editingId)?.api_token_masked || "не сохранён"}
              </p>
            ) : (
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                Сохраните токен, затем заполните поля отправителя и нажмите сохранить профиль.
              </p>
            )}
          </div>

          <div ref={counterpartyLookupRootRef} className="relative">
            <input
              className="h-10 w-full rounded-md border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              placeholder="Контрагент"
              value={counterpartyQuery}
              onChange={(event) => {
                const next = event.target.value;
                setCounterpartyQuery(next);
                setForm((prev) => ({ ...prev, counterparty_ref: next }));
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setCounterparties([]);
                  setActiveCounterpartyIndex(-1);
                  return;
                }
                if (!counterparties.length) {
                  return;
                }
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveCounterpartyIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, counterparties.length - 1)));
                  return;
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveCounterpartyIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                  return;
                }
                if (event.key === "Enter") {
                  event.preventDefault();
                  const resolvedIndex = activeCounterpartyIndex >= 0 ? activeCounterpartyIndex : 0;
                  const selected = counterparties[resolvedIndex];
                  if (selected) {
                    onCounterpartySelect(selected);
                  }
                }
              }}
            />
            {counterparties.length ? (
              <div
                className="absolute left-0 right-0 top-11 z-20 max-h-40 overflow-auto rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                role="listbox"
                aria-label="Контрагенты"
              >
                {counterparties.map((row, index) => (
                  <button
                    key={row.ref}
                    type="button"
                    data-nav-scope="counterparty"
                    data-nav-index={index}
                    className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
                    style={{
                      borderColor: "var(--border)",
                      backgroundColor: index === activeCounterpartyIndex ? "var(--surface-2)" : "var(--surface)",
                    }}
                    role="option"
                    aria-selected={index === activeCounterpartyIndex}
                    onMouseEnter={() => setActiveCounterpartyIndex(index)}
                    onClick={() => onCounterpartySelect(row)}
                  >
                    <span className="truncate font-medium">{row.label}</span>
                  </button>
                ))}
              </div>
            ) : null}
            <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
              {!editingId
                ? "Сначала сохраните токен отправителя."
                : counterpartyLoading
                  ? "Ищем контрагентов..."
                  : counterpartyDetailsLoading
                    ? "Подтягиваем телефон и адрес..."
                    : form.counterparty_ref
                      ? "Контрагент выбран."
                      : "Введите минимум 2 символа для поиска."}
            </p>
          </div>

          <input className="h-10 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} placeholder={t("orders.modals.waybill.settings.form.phone")} value={form.phone} onChange={(event) => setForm((prev) => ({ ...prev, phone: event.target.value }))} />
          <input className="h-10 rounded-md border px-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }} placeholder="ФИО" value={form.contact_name} onChange={(event) => setForm((prev) => ({ ...prev, contact_name: event.target.value }))} />

          <div ref={modalCityLookupRootRef} className="relative">
            <input
              className="h-10 w-full rounded-md border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              placeholder="Город"
              value={modalCityQuery}
              onChange={(event) => {
                const next = event.target.value;
                setModalCityQuery(next);
                setForm((prev) => ({ ...prev, city_ref: "" }));
                setSelectedSettlementRef("");
                setModalAddresses([]);
                setActiveModalAddressIndex(-1);
                setModalAddressQuery("");
                setSelectedModalAddressRef("");
                setSelectedModalAddressLabel("");
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setModalCities([]);
                  setActiveModalCityIndex(-1);
                  return;
                }
                if (!modalCities.length) {
                  return;
                }
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveModalCityIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, modalCities.length - 1)));
                  return;
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveModalCityIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                  return;
                }
                if (event.key === "Enter") {
                  event.preventDefault();
                  const resolvedIndex = activeModalCityIndex >= 0 ? activeModalCityIndex : 0;
                  const selected = modalCities[resolvedIndex];
                  if (selected) {
                    onModalCitySelect(selected);
                  }
                }
              }}
            />
            {modalCities.length ? (
              <div
                className="absolute left-0 right-0 top-11 z-20 max-h-48 overflow-auto rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                role="listbox"
                aria-label="Города"
              >
                {modalCities.map((item, index) => (
                  <button
                    key={item.ref}
                    type="button"
                    data-nav-scope="modal-city"
                    data-nav-index={index}
                    className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
                    style={{
                      borderColor: "var(--border)",
                      backgroundColor: index === activeModalCityIndex ? "var(--surface-2)" : "var(--surface)",
                    }}
                    role="option"
                    aria-selected={index === activeModalCityIndex}
                    onMouseEnter={() => setActiveModalCityIndex(index)}
                    onClick={() => onModalCitySelect(item)}
                  >
                    <span className="truncate font-medium">{item.label}</span>
                  </button>
                ))}
              </div>
            ) : null}
            <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
              {!editingId ? "Сначала сохраните токен отправителя." : modalCityLoading ? "Ищем города..." : "Введите минимум 2 символа."}
            </p>
          </div>

          <div ref={modalAddressLookupRootRef} className="relative md:col-span-2">
            <input
              className="h-10 w-full rounded-md border px-3 text-sm"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
              placeholder="Отделение / почтомат / адрес"
              value={modalAddressQuery}
              onChange={(event) => {
                const next = event.target.value;
                setModalAddressQuery(next);
                setModalAddresses([]);
                setActiveModalAddressIndex(-1);
                const basePart = next.split(",")[0]?.trim().toLowerCase() ?? "";
                const selectedBase = selectedModalAddressLabel.trim().toLowerCase();
                const keepSelectedRef = Boolean(selectedModalAddressRef && selectedBase && basePart === selectedBase);
                if (keepSelectedRef) {
                  setForm((prev) => ({ ...prev, address_ref: selectedModalAddressRef }));
                  return;
                }
                setSelectedModalAddressRef("");
                setSelectedModalAddressLabel("");
                setForm((prev) => ({ ...prev, address_ref: next }));
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setModalAddresses([]);
                  setActiveModalAddressIndex(-1);
                  return;
                }
                if (!modalAddresses.length) {
                  return;
                }
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveModalAddressIndex((prev) => (prev < 0 ? 0 : Math.min(prev + 1, modalAddresses.length - 1)));
                  return;
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveModalAddressIndex((prev) => (prev <= 0 ? 0 : prev - 1));
                  return;
                }
                if (event.key === "Enter") {
                  event.preventDefault();
                  const resolvedIndex = activeModalAddressIndex >= 0 ? activeModalAddressIndex : 0;
                  const selected = modalAddresses[resolvedIndex];
                  if (selected) {
                    onModalAddressSelect(selected);
                  }
                }
              }}
            />
            {modalAddresses.length ? (
              <div
                className="absolute left-0 right-0 top-11 z-20 max-h-48 overflow-auto rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                role="listbox"
                aria-label="Отделения и адреса"
              >
                {modalAddresses.map((item, index) => (
                  <button
                    key={item.ref}
                    type="button"
                    data-nav-scope="modal-address"
                    data-nav-index={index}
                    className="flex h-10 w-full items-center border-b px-3 text-left text-sm last:border-b-0"
                    style={{
                      borderColor: "var(--border)",
                      backgroundColor: index === activeModalAddressIndex ? "var(--surface-2)" : "var(--surface)",
                    }}
                    role="option"
                    aria-selected={index === activeModalAddressIndex}
                    onMouseEnter={() => setActiveModalAddressIndex(index)}
                    onClick={() => onModalAddressSelect(item)}
                  >
                    <span className="truncate font-medium">{item.label}</span>
                    {item.subtitle ? (
                      <span className="ml-2 shrink-0 text-[11px]" style={{ color: "var(--muted)" }}>
                        {item.subtitle}
                      </span>
                    ) : null}
                  </button>
                ))}
              </div>
            ) : null}
            <p className="mt-1 text-[11px]" style={{ color: "var(--muted)" }}>
              {!editingId
                ? "Сначала сохраните токен отправителя."
                : modalAddressLoading
                  ? "Ищем отделения/почтоматы/адреса..."
                  : "Цифры: отделения/почтоматы. Буквы: улицы. Дом укажите после запятой."}
            </p>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-end gap-2">
          <div className="mr-auto flex items-center gap-2">
            <label
              className="inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold"
              style={{
                borderColor: form.is_active ? "#16a34a" : "var(--border)",
                backgroundColor: form.is_active ? "#166534" : "var(--surface-2)",
                color: form.is_active ? "#ffffff" : "var(--text)",
              }}
            >
              <input
                type="checkbox"
                className="mr-2 h-3.5 w-3.5"
                checked={form.is_active}
                style={{ accentColor: "#22c55e" }}
                onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))}
              />
              {t("orders.modals.waybill.settings.form.active")}
            </label>
            <label
              className="inline-flex h-9 items-center rounded-md border px-3 text-xs font-semibold"
              style={{
                borderColor: form.is_default ? "#2563eb" : "var(--border)",
                backgroundColor: form.is_default ? "#1d4ed8" : "var(--surface-2)",
                color: form.is_default ? "#ffffff" : "var(--text)",
              }}
            >
              <input
                type="checkbox"
                className="mr-2 h-3.5 w-3.5"
                checked={form.is_default}
                style={{ accentColor: "#3b82f6" }}
                onChange={(event) => setForm((prev) => ({ ...prev, is_default: event.target.checked }))}
              />
              {t("orders.modals.waybill.settings.form.default")}
            </label>
          </div>
          <button
            type="submit"
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "#2563eb", color: "#fff" }}
            disabled={saving}
          >
            <Plus className="h-4 w-4" />
            {saving ? t("loading") : editingId ? t("orders.modals.waybill.settings.actions.update") : t("orders.modals.waybill.settings.actions.create")}
          </button>
        </div>
      </form>
    </div>
  );
}
