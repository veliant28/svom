const WS_RE = /[\n\r\t]+/g;
const MULTI_SPACE_RE = /\s+/g;

export function normalizeDisplayText(value: string | null | undefined): string {
  return String(value || "").replace(WS_RE, " ").replace(MULTI_SPACE_RE, " ").trim();
}
