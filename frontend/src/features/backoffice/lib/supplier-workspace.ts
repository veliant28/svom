export function formatBackofficeDate(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function formatSupplierError(value: string | null | undefined, fallback: string) {
  if (!value) {
    return "-";
  }

  const normalized = value
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!normalized) {
    return "-";
  }

  if (/(traceback|stack trace|<!doctype html|<html|notsupportederror|jsondecodeerror|sqlstate)/i.test(normalized)) {
    return fallback;
  }

  return normalized.length > 180 ? `${normalized.slice(0, 177)}...` : normalized;
}
