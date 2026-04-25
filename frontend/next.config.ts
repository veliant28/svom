import createNextIntlPlugin from "next-intl/plugin";
import type { NextConfig } from "next";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

function getBackendImageRemotePattern() {
  const rawApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
  const backendUrl = new URL(rawApiBaseUrl.replace(/\/api\/?$/, ""));

  return {
    protocol: backendUrl.protocol.replace(":", "") as "http" | "https",
    hostname: backendUrl.hostname,
    port: backendUrl.port,
    pathname: "/media/**",
  };
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [getBackendImageRemotePattern()],
  },
};

export default withNextIntl(nextConfig);
