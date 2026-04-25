import type { BackofficeVchasnoKasaSettings } from "@/features/backoffice/types/vchasno-kasa.types";

export type SettingsForm = {
  is_enabled: boolean;
  api_token: string;
  fiscal_api_token: string;
  rro_fn: string;
  default_payment_type: number;
  default_tax_group: string;
  selected_payment_methods: string[];
  selected_tax_groups: string[];
  auto_issue_on_completed: boolean;
  send_customer_email: boolean;
};

export const DEFAULT_FORM: SettingsForm = {
  is_enabled: false,
  api_token: "",
  fiscal_api_token: "",
  rro_fn: "",
  default_payment_type: 1,
  default_tax_group: "",
  selected_payment_methods: [],
  selected_tax_groups: [],
  auto_issue_on_completed: true,
  send_customer_email: true,
};

export function normalizeCodes(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of values) {
    const code = String(raw || "").normalize("NFKC").trim().toUpperCase();
    if (!code || seen.has(code)) {
      continue;
    }
    seen.add(code);
    result.push(code);
  }
  return result;
}

export function toVchasnoKasaSettingsForm(settings: BackofficeVchasnoKasaSettings | null): SettingsForm {
  if (!settings) {
    return DEFAULT_FORM;
  }
  const selectedPaymentMethods = normalizeCodes(settings.selected_payment_methods || []);
  const selectedTaxGroups = normalizeCodes(settings.selected_tax_groups || []);
  return {
    is_enabled: settings.is_enabled,
    api_token: "",
    fiscal_api_token: "",
    rro_fn: settings.rro_fn || "",
    default_payment_type: settings.default_payment_type || 1,
    default_tax_group: settings.default_tax_group || "",
    selected_payment_methods: selectedPaymentMethods,
    selected_tax_groups: selectedTaxGroups,
    auto_issue_on_completed: settings.auto_issue_on_completed,
    send_customer_email: settings.send_customer_email,
  };
}

export function arraysEqual(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((item, index) => item === right[index]);
}

export function resolveStatusLabel(statusKey: string, t: (key: string) => string): string {
  const translationKey = `vchasnoKasa.receiptStatus.${statusKey || "pending"}`;
  const translated = t(translationKey);
  return translated === translationKey ? t("vchasnoKasa.receiptStatus.pending") : translated;
}

export function resolveShiftStatusLabel(statusKey: string, t: (key: string) => string): string {
  const translationKey = `vchasnoKasa.shift.statuses.${statusKey || "unknown"}`;
  const translated = t(translationKey);
  return translated === translationKey ? t("vchasnoKasa.shift.statuses.unknown") : translated;
}

export function resolveShiftMessage(message: string, t: (key: string) => string): string {
  const normalized = String(message || "").trim();
  if (!normalized) {
    return "";
  }
  const knownMessages: Record<string, string> = {
    "Зміну відкрито.": "vchasnoKasa.shift.messages.opened",
    "Зміну закрито.": "vchasnoKasa.shift.messages.closed",
    "Інтеграцію Вчасно.Каса вимкнено.": "vchasnoKasa.shift.messages.disabled",
    "Не вдалося визначити стан зміни.": "vchasnoKasa.shift.messages.unknown",
    "Помилка перевірки стану зміни.": "vchasnoKasa.shift.messages.error",
    "API токен каси Вчасно не задан (Налаштування каси -> Токен).": "vchasnoKasa.shift.messages.tokenMissing",
    "Unauthorized": "vchasnoKasa.shift.messages.unauthorized",
    "Forbidden": "vchasnoKasa.shift.messages.unauthorized",
    "Неавторизовано у Вчасно.Каса. Перевірте API токен каси (Налаштування каси → API → Згенерувати) і права токена на фіскальні операції.":
      "vchasnoKasa.shift.messages.unauthorized",
  };
  const translationKey = knownMessages[normalized];
  if (!translationKey) {
    return normalized;
  }
  const translated = t(translationKey);
  return translated === translationKey ? normalized : translated;
}

export function resolveConnectionCheckMessage(message: string, t: (key: string) => string): string {
  const normalized = String(message || "").trim();
  if (!normalized) {
    return "";
  }
  const knownMessages: Record<string, string> = {
    "Connection successful.": "vchasnoKasa.messages.connectionOk",
    "Підключення успішне.": "vchasnoKasa.messages.connectionOk",
    "Проверка подключения успешна.": "vchasnoKasa.messages.connectionOk",
    "Вчасно.Каса выключена.": "vchasnoKasa.messages.integrationDisabled",
    "API токен замовлень Вчасно не задан (Налаштування компанії -> Інтеграція замовлень -> API).":
      "vchasnoKasa.messages.tokenMissing",
    "Фискальный номер РРО/ПРРО не задан.": "vchasnoKasa.messages.rroMissing",
    "Не удалось подключиться к Вчасно.Каса.": "vchasnoKasa.messages.connectionUnavailable",
  };
  const translationKey = knownMessages[normalized];
  if (!translationKey) {
    return normalized;
  }
  const translated = t(translationKey);
  return translated === translationKey ? normalized : translated;
}

export function resolveLastCheckMessage(message: string, t: (key: string) => string): string {
  const resolved = resolveConnectionCheckMessage(message, t);
  if (!resolved) {
    return "-";
  }
  return resolved;
}

export function formatDateTime(value: string | null | undefined, locale: string): string {
  const raw = String(value || "").trim();
  if (!raw) {
    return "-";
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(parsed);
}
