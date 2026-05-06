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
  async rewrites() {
    const rawApiBaseUrl = process.env.NEXT_SERVER_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
    const apiBaseUrl = rawApiBaseUrl.replace(/\/+$/, "");
    const backendBaseUrl = apiBaseUrl.replace(/\/api$/, "");
    return [
      {
        source: "/media/:path*",
        destination: `${backendBaseUrl}/media/:path*`,
      },
      {
        source: "/:locale(uk|ru|en)/media/:path*",
        destination: `${backendBaseUrl}/media/:path*`,
      },
      {
        source: "/:locale(uk|ru|en)/backend-api/media/:path*",
        destination: `${backendBaseUrl}/media/:path*`,
      },
      {
        source: "/backend-api/media/:path*",
        destination: `${backendBaseUrl}/media/:path*`,
      },
      {
        source: "/:locale(uk|ru|en)/backend-api/:path*",
        destination: `${apiBaseUrl}/:path*/`,
      },
      {
        source: "/backend-api/:path*",
        destination: `${apiBaseUrl}/:path*/`,
      },
      {
        source: "/:locale(uk|ru|en)/api/:path*",
        destination: `${apiBaseUrl}/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${apiBaseUrl}/:path*/`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
