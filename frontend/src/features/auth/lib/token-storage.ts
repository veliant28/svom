import { AUTH_TOKEN_COOKIE_KEY, AUTH_TOKEN_STORAGE_KEY } from "@/features/auth/lib/auth-token-constants";

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function writeAuthCookie(token: string): void {
  if (typeof document === "undefined") {
    return;
  }
  document.cookie = `${AUTH_TOKEN_COOKIE_KEY}=${encodeURIComponent(token)}; Path=/; Max-Age=2592000; SameSite=Lax`;
}

function clearAuthCookie(): void {
  if (typeof document === "undefined") {
    return;
  }
  document.cookie = `${AUTH_TOKEN_COOKIE_KEY}=; Path=/; Max-Age=0; SameSite=Lax`;
}

function readAuthCookie(): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const prefix = `${AUTH_TOKEN_COOKIE_KEY}=`;
  const raw = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix));

  if (!raw) {
    return null;
  }

  const value = raw.slice(prefix.length);
  if (!value) {
    return null;
  }

  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function readStoredAuthToken(): string | null {
  if (!canUseStorage()) {
    return null;
  }

  const cookieToken = readAuthCookie();
  if (cookieToken) {
    if (window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) !== cookieToken) {
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, cookieToken);
    }
    return cookieToken;
  }

  const storageToken = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  if (storageToken) {
    writeAuthCookie(storageToken);
    return storageToken;
  }

  return null;
}

export function writeStoredAuthToken(token: string): void {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  writeAuthCookie(token);
}

export function clearStoredAuthToken(): void {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  clearAuthCookie();
}
