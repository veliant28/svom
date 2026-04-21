import { isApiRequestError } from "@/shared/api/http-client";

type BackofficeErrorTranslator = (key: string, values?: Record<string, string | number>) => string;

export type NormalizedBackofficeError = {
  variant: "error" | "warning";
  message: string;
};

function extractMessageCandidates(value: unknown, depth = 0): string[] {
  if (depth > 2 || value == null) {
    return [];
  }

  if (typeof value === "string") {
    return [value];
  }

  if (Array.isArray(value)) {
    return value.flatMap((item) => extractMessageCandidates(item, depth + 1));
  }

  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const prioritizedKeys = ["detail", "message", "error", "non_field_errors", "errors"];

    const prioritized = prioritizedKeys.flatMap((key) => extractMessageCandidates(record[key], depth + 1));
    if (prioritized.length > 0) {
      return prioritized;
    }

    return Object.values(record).flatMap((item) => extractMessageCandidates(item, depth + 1));
  }

  return [];
}

function parseJsonString(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
    return undefined;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return undefined;
  }
}

function sanitizeErrorMessage(raw: string): string {
  const parsed = parseJsonString(raw);
  if (parsed !== undefined) {
    const fromJson = extractMessageCandidates(parsed).find((item) => item.trim().length > 0);
    if (fromJson) {
      return sanitizeErrorMessage(fromJson);
    }
  }

  return raw
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, "\"")
    .replace(/\s+/g, " ")
    .trim();
}

function looksTechnical(text: string): boolean {
  if (!text) {
    return true;
  }

  const lower = text.toLowerCase();
  if (
    lower.includes("traceback")
    || lower.includes("stack trace")
    || lower.includes("notsupportederror")
    || lower.includes("<!doctype html")
    || lower.includes("<html")
    || lower.includes("sqlstate")
    || lower.includes("jsondecodeerror")
    || lower.includes("internal server error")
  ) {
    return true;
  }

  if (/^\s*api request failed with\s+\d{3}\s*$/i.test(text)) {
    return true;
  }

  return false;
}

function pickPositiveNumber(...values: unknown[]): number | null {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) {
      return Math.ceil(value);
    }
    if (typeof value === "string") {
      const numeric = Number(value);
      if (Number.isFinite(numeric) && numeric > 0) {
        return Math.ceil(numeric);
      }
    }
  }
  return null;
}

function secondsUntil(value: unknown): number | null {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  const delta = Math.ceil((date.getTime() - Date.now()) / 1000);
  return delta > 0 ? delta : null;
}

function extractRetryAfterSeconds(payload: Record<string, unknown> | undefined, fallbackText: string): number | null {
  const payloadSeconds = pickPositiveNumber(
    payload?.retry_after,
    payload?.retry_after_seconds,
    payload?.seconds,
    payload?.wait_seconds,
    payload?.cooldown_wait_seconds,
  );
  if (payloadSeconds) {
    return payloadSeconds;
  }

  const payloadNextAllowedSeconds = pickPositiveNumber(
    secondsUntil(payload?.next_allowed_at),
    secondsUntil(payload?.next_allowed_request_at),
  );
  if (payloadNextAllowedSeconds) {
    return payloadNextAllowedSeconds;
  }

  const match = fallbackText.match(/(\d{1,6})\s*(sec|secs|second|seconds|сек|секунд|с)\b/i);
  if (match) {
    return pickPositiveNumber(match[1]);
  }

  return null;
}

function isCooldownError(status: number | undefined, message: string, seconds: number | null): boolean {
  if (seconds && seconds > 0) {
    return true;
  }
  const hasCooldownMarker = /(cooldown|too many requests|rate limit|throttl|забагато запитів|занадто рано|слишком рано)/i.test(message);
  if (status === 429) {
    return true;
  }
  if (typeof status === "number") {
    return false;
  }
  return hasCooldownMarker;
}

export function normalizeBackofficeApiError(
  error: unknown,
  options: {
    t: BackofficeErrorTranslator;
    fallbackMessage?: string;
  },
): NormalizedBackofficeError {
  const fallbackMessage = options.fallbackMessage ?? options.t("defaultAction");

  if (isApiRequestError(error)) {
    if (error.isNetworkError) {
      return { variant: "error", message: options.t("network") };
    }

    const payload = error.payload as Record<string, unknown> | undefined;
    const candidates = [
      ...extractMessageCandidates(payload),
      error.message,
    ];
    const firstMessage = candidates.find((item) => item.trim().length > 0) ?? "";
    const sanitizedMessage = sanitizeErrorMessage(firstMessage);
    const retryAfterSeconds = extractRetryAfterSeconds(payload, sanitizedMessage);

    if (isCooldownError(error.status, sanitizedMessage, retryAfterSeconds)) {
      if (retryAfterSeconds) {
        return {
          variant: "warning",
          message: options.t("cooldownSeconds", { seconds: retryAfterSeconds }),
        };
      }
      return {
        variant: "warning",
        message: options.t("cooldown"),
      };
    }

    if (error.status && [502, 503, 504].includes(error.status)) {
      return {
        variant: "error",
        message: options.t("supplierUnavailable"),
      };
    }

    if (sanitizedMessage && !looksTechnical(sanitizedMessage) && sanitizedMessage.length <= 220) {
      return {
        variant: "error",
        message: sanitizedMessage,
      };
    }

    return {
      variant: "error",
      message: fallbackMessage,
    };
  }

  if (error instanceof Error) {
    const sanitizedMessage = sanitizeErrorMessage(error.message);
    const retryAfterSeconds = extractRetryAfterSeconds(undefined, sanitizedMessage);

    if (isCooldownError(undefined, sanitizedMessage, retryAfterSeconds)) {
      if (retryAfterSeconds) {
        return {
          variant: "warning",
          message: options.t("cooldownSeconds", { seconds: retryAfterSeconds }),
        };
      }
      return {
        variant: "warning",
        message: options.t("cooldown"),
      };
    }

    if (sanitizedMessage && !looksTechnical(sanitizedMessage) && sanitizedMessage.length <= 220) {
      return { variant: "error", message: sanitizedMessage };
    }
  }

  return {
    variant: "error",
    message: fallbackMessage,
  };
}
