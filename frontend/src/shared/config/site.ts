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

const rawApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const apiBaseUrl = normalizeApiBaseUrl(rawApiBaseUrl);
const serverApiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_SERVER_API_BASE_URL ?? rawApiBaseUrl);

export const siteConfig = {
  name: "SVOM",
  apiBaseUrl,
  serverApiBaseUrl,
  backendBaseUrl: deriveBackendBaseUrl(apiBaseUrl),
  serverBackendBaseUrl: deriveBackendBaseUrl(serverApiBaseUrl),
};

export function getRuntimeApiBaseUrl(): string {
  return typeof window === "undefined" ? siteConfig.serverApiBaseUrl : siteConfig.apiBaseUrl;
}
