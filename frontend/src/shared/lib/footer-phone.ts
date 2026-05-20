export type FooterPhoneFormat = "mobile" | "toll_free_0800";

const FOOTER_PHONE_DIGITS = 10;

function normalizeFormat(value: string | null | undefined): FooterPhoneFormat {
  return value === "toll_free_0800" ? "toll_free_0800" : "mobile";
}

function normalizeMobileDigits(digits: string): string {
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
      return rest.slice(0, FOOTER_PHONE_DIGITS);
    }
    return `0${rest}`.slice(0, FOOTER_PHONE_DIGITS);
  }
  if (digits.startsWith("0")) {
    return digits.slice(0, FOOTER_PHONE_DIGITS);
  }
  if (digits.length >= FOOTER_PHONE_DIGITS) {
    const tail = digits.slice(-FOOTER_PHONE_DIGITS);
    return tail.startsWith("0") ? tail : `0${tail}`.slice(0, FOOTER_PHONE_DIGITS);
  }
  return `0${digits}`.slice(0, FOOTER_PHONE_DIGITS);
}

function normalizeTollFreeDigits(digits: string): string {
  if (!digits) {
    return "";
  }
  if (digits.startsWith("380800")) {
    return `0${digits.slice(3)}`.slice(0, FOOTER_PHONE_DIGITS);
  }
  if (digits.startsWith("800")) {
    return `0${digits}`.slice(0, FOOTER_PHONE_DIGITS);
  }
  if (digits.startsWith("0800")) {
    return digits.slice(0, FOOTER_PHONE_DIGITS);
  }
  if (digits.length >= 6) {
    return `0800${digits.slice(-6)}`.slice(0, FOOTER_PHONE_DIGITS);
  }
  return `0800${digits}`.slice(0, FOOTER_PHONE_DIGITS);
}

export function normalizeFooterPhoneDigits(
  value: string,
  phoneFormat: FooterPhoneFormat = "mobile",
): string {
  const digits = String(value || "").replace(/\D+/g, "");
  if (!digits) {
    return "";
  }
  const normalizedFormat = normalizeFormat(phoneFormat);
  if (normalizedFormat === "toll_free_0800") {
    return normalizeTollFreeDigits(digits);
  }
  return normalizeMobileDigits(digits);
}

export function formatFooterPhoneForInput(
  value: string,
  phoneFormat: FooterPhoneFormat = "mobile",
): string {
  const normalizedFormat = normalizeFormat(phoneFormat);
  const normalized = normalizeFooterPhoneDigits(value, normalizedFormat);
  if (!normalized) {
    return "";
  }
  if (normalizedFormat === "toll_free_0800") {
    const code = normalized.slice(1, 4);
    const left = normalized.slice(4, 7);
    const right = normalized.slice(7, 10);
    let out = "0";
    if (code) {
      out += ` (${code}`;
      if (code.length === 3) {
        out += ")";
      }
    }
    if (left) {
      out += code.length === 3 ? ` ${left}` : left;
    }
    if (right) {
      out += `-${right}`;
    }
    return out;
  }

  const operator = normalized.slice(0, 3);
  const left = normalized.slice(3, 6);
  const middle = normalized.slice(6, 8);
  const right = normalized.slice(8, 10);

  let out = "38";
  if (operator) {
    out += ` (${operator}`;
    if (operator.length === 3) {
      out += ")";
    }
  }
  if (left) {
    out += operator.length === 3 ? ` ${left}` : left;
  }
  if (middle) {
    out += `-${middle}`;
  }
  if (right) {
    out += `-${right}`;
  }
  return out;
}

export function formatFooterPhoneForSave(
  value: string,
  phoneFormat: FooterPhoneFormat = "mobile",
): string {
  const normalizedFormat = normalizeFormat(phoneFormat);
  const normalized = normalizeFooterPhoneDigits(value, normalizedFormat);
  if (!normalized || normalized.length !== FOOTER_PHONE_DIGITS) {
    return "";
  }
  if (normalizedFormat === "toll_free_0800" && !normalized.startsWith("0800")) {
    return "";
  }
  return formatFooterPhoneForInput(normalized, normalizedFormat);
}

export function formatFooterPhoneDisplay(
  value: string,
  phoneFormat: FooterPhoneFormat = "mobile",
): string {
  const normalizedFormat = normalizeFormat(phoneFormat);
  const normalized = normalizeFooterPhoneDigits(value, normalizedFormat);
  if (normalized.length === FOOTER_PHONE_DIGITS) {
    if (normalizedFormat === "toll_free_0800" && !normalized.startsWith("0800")) {
      return String(value || "").trim();
    }
    return formatFooterPhoneForInput(normalized, normalizedFormat);
  }
  return String(value || "").trim();
}
