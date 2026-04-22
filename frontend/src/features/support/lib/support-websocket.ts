import { siteConfig } from "@/shared/config/site";

export function buildSupportWebSocketUrl(path: string, token: string): string {
  const base = new URL(siteConfig.backendBaseUrl);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = path;
  base.searchParams.set("token", token);
  return base.toString();
}
