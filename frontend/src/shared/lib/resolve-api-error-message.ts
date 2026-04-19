import { isApiRequestError } from "@/shared/api/http-client";

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

export function resolveApiErrorMessage(error: unknown, fallbackMessage: string): string {
  if (!isApiRequestError(error)) {
    return fallbackMessage;
  }

  const payload = error.payload;
  if (!payload || typeof payload !== "object") {
    return error.message?.trim() || fallbackMessage;
  }

  return extractStringFromPayload(payload as Record<string, unknown>) || error.message?.trim() || fallbackMessage;
}

