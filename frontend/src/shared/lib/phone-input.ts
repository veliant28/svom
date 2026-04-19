export const PHONE_INPUT_PLACEHOLDER = "38 (0XX) XXX-XX-XX";
export const PHONE_INPUT_REGEX = /^38 \(0\d{2}\) \d{3}-\d{2}-\d{2}$/;
export const PHONE_INPUT_MAX_LENGTH = 18;

function normalizeLocalPhoneDigits(value: string): string {
  const digitsOnly = value.replace(/\D/g, "");
  if (!digitsOnly) {
    return "";
  }
  if (digitsOnly === "3" || digitsOnly === "38") {
    return "";
  }

  if (digitsOnly.startsWith("380")) {
    return `0${digitsOnly.slice(3)}`.slice(0, 10);
  }
  if (digitsOnly.startsWith("38")) {
    const tail = digitsOnly.slice(2);
    if (tail.startsWith("0")) {
      return tail.slice(0, 10);
    }
    return `0${tail}`.slice(0, 10);
  }
  if (digitsOnly.startsWith("0")) {
    return digitsOnly.slice(0, 10);
  }
  return `0${digitsOnly}`.slice(0, 10);
}

export function formatPhoneInput(value: string): string {
  const localDigits = normalizeLocalPhoneDigits(value);
  if (!localDigits) {
    return "";
  }

  let output = "38 (";
  output += localDigits.slice(0, Math.min(3, localDigits.length));
  if (localDigits.length > 3) {
    output += ")";
  }
  if (localDigits.length > 3) {
    output += ` ${localDigits.slice(3, 6)}`;
  }
  if (localDigits.length > 6) {
    output += `-${localDigits.slice(6, 8)}`;
  }
  if (localDigits.length > 8) {
    output += `-${localDigits.slice(8, 10)}`;
  }
  return output;
}

export function isPhoneInputValid(value: string): boolean {
  return PHONE_INPUT_REGEX.test(value.trim());
}
