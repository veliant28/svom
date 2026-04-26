import { isApiRequestError } from "@/shared/api/http-client";

const CYRILLIC_REGEX = /[А-Яа-яЁёІіЇїЄєҐґ]/;

type KnownStorefrontApiErrorMessages = {
  phoneFormat: string;
  required: string;
  notBlank: string;
  invalidEmail: string;
  emailAlreadyExists: string;
  invalidChoice: string;
  currentPasswordIncorrect: string;
  maxLength: (max: number) => string;
  minLength: (min: number) => string;
  exactLength: (count: number) => string;
};

type ResolveApiErrorMessageOptions = {
  knownMessages?: KnownStorefrontApiErrorMessages;
};

function sanitizeMessage(raw: string): string {
  return raw
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function looksTechnical(text: string): boolean {
  const lower = text.toLowerCase();
  return (
    lower.includes("traceback")
    || lower.includes("stack trace")
    || lower.includes("internal server error")
    || lower.includes("<!doctype html")
    || lower.includes("<html")
    || /^api request failed with\s+\d{3}$/i.test(text)
  );
}

function shouldUseFallback(rawMessage: string, fallbackMessage: string): boolean {
  const sanitized = sanitizeMessage(rawMessage);
  if (!sanitized || looksTechnical(sanitized)) {
    return true;
  }

  const fallbackHasCyrillic = CYRILLIC_REGEX.test(fallbackMessage);
  const messageHasCyrillic = CYRILLIC_REGEX.test(sanitized);

  // For RU/UK interfaces prefer localized fallback over English backend errors.
  if (fallbackHasCyrillic && !messageHasCyrillic) {
    return true;
  }

  return false;
}

function extractStringFromPayload(payload: Record<string, unknown>): string | null {
  const detail = payload.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  const message = payload.message;
  if (typeof message === "string" && message.trim()) {
    return message.trim();
  }

  for (const value of Object.values(payload)) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    if (Array.isArray(value)) {
      const firstText = value.find((item) => typeof item === "string" && item.trim());
      if (typeof firstText === "string") {
        return firstText.trim();
      }
    }
  }

  return null;
}

function resolveKnownApiErrorMessage(
  rawMessage: string,
  knownMessages?: KnownStorefrontApiErrorMessages,
): string | null {
  if (!knownMessages) {
    return null;
  }

  const sanitized = sanitizeMessage(rawMessage);
  if (!sanitized) {
    return null;
  }

  if (/^phone must match format 38\(0xx\)xxx-xx-xx\.?$/i.test(sanitized)) {
    return knownMessages.phoneFormat;
  }
  if (/^this field is required\.?$/i.test(sanitized)) {
    return knownMessages.required;
  }
  if (/^this field may not be blank\.?$/i.test(sanitized)) {
    return knownMessages.notBlank;
  }
  if (/^enter a valid email address\.?$/i.test(sanitized)) {
    return knownMessages.invalidEmail;
  }
  if (/^a user with this email already exists\.?$/i.test(sanitized)) {
    return knownMessages.emailAlreadyExists;
  }
  if (/^current password is incorrect\.?$/i.test(sanitized)) {
    return knownMessages.currentPasswordIncorrect;
  }
  if (/^(select a valid choice|\".+\" is not a valid choice)\.?$/i.test(sanitized)) {
    return knownMessages.invalidChoice;
  }

  const maxLengthMatch = sanitized.match(
    /^ensure this (?:value|field) has (?:at most|no more than) (\d+) characters(?:\s*\(.*\))?\.?$/i,
  );
  if (maxLengthMatch) {
    return knownMessages.maxLength(Number(maxLengthMatch[1]));
  }

  const minLengthMatch = sanitized.match(
    /^ensure this (?:value|field) has at least (\d+) characters(?:\s*\(.*\))?\.?$/i,
  );
  if (minLengthMatch) {
    return knownMessages.minLength(Number(minLengthMatch[1]));
  }

  const exactLengthMatch = sanitized.match(
    /^ensure this (?:value|field) has exactly (\d+) characters(?:\s*\(.*\))?\.?$/i,
  );
  if (exactLengthMatch) {
    return knownMessages.exactLength(Number(exactLengthMatch[1]));
  }

  return null;
}

export function resolveApiErrorMessage(
  error: unknown,
  fallbackMessage: string,
  options?: ResolveApiErrorMessageOptions,
): string {
  if (!isApiRequestError(error)) {
    return fallbackMessage;
  }

  if (error.isNetworkError) {
    return fallbackMessage;
  }

  const payload = error.payload;
  if (!payload || typeof payload !== "object") {
    const directMessage = error.message?.trim();
    const localizedKnownMessage = directMessage
      ? resolveKnownApiErrorMessage(directMessage, options?.knownMessages)
      : null;
    if (localizedKnownMessage) {
      return localizedKnownMessage;
    }
    if (!directMessage || shouldUseFallback(directMessage, fallbackMessage)) {
      return fallbackMessage;
    }
    return sanitizeMessage(directMessage);
  }

  const payloadMessage = extractStringFromPayload(payload as Record<string, unknown>) || error.message?.trim() || "";
  const localizedKnownMessage = resolveKnownApiErrorMessage(payloadMessage, options?.knownMessages);
  if (localizedKnownMessage) {
    return localizedKnownMessage;
  }
  if (!payloadMessage || shouldUseFallback(payloadMessage, fallbackMessage)) {
    return fallbackMessage;
  }
  return sanitizeMessage(payloadMessage);
}
