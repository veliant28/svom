const FOOTER_PHONE_DIGITS = 10;

export function normalizeFooterPhoneDigits(value: string): string {
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

export function formatFooterPhoneForInput(value: string): string {
  const normalized = normalizeFooterPhoneDigits(value);
  if (!normalized) {
    return "";
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

export function formatFooterPhoneForSave(value: string): string {
  const normalized = normalizeFooterPhoneDigits(value);
  if (!normalized || normalized.length !== FOOTER_PHONE_DIGITS) {
    return "";
  }
  return formatFooterPhoneForInput(normalized);
}

export function formatFooterPhoneDisplay(value: string): string {
  const normalized = normalizeFooterPhoneDigits(value);
  if (normalized.length === FOOTER_PHONE_DIGITS) {
    return formatFooterPhoneForInput(normalized);
  }
  return String(value || "").trim();
}
