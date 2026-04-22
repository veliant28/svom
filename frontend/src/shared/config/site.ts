function normalizeApiBaseUrl(input: string): string {
  const trimmed = input.trim().replace(/\/+$/, "");
  if (trimmed.endsWith("/api")) {
    return trimmed;
  }
  return `${trimmed}/api`;
}

function deriveBackendBaseUrl(apiBaseUrl: string): string {
  return apiBaseUrl.replace(/\/api$/, "");
}

const rawApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";
const apiBaseUrl = normalizeApiBaseUrl(rawApiBaseUrl);

export const siteConfig = {
  name: "SVOM",
  apiBaseUrl,
  backendBaseUrl: deriveBackendBaseUrl(apiBaseUrl),
};
