import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { AUTH_TOKEN_COOKIE_KEY } from "@/features/auth/lib/auth-token-constants";
import { hasBackofficeCapabilities, type BackofficeCapabilityCode } from "@/features/backoffice/lib/capabilities";
import type { BackofficeUser } from "@/features/backoffice/types/backoffice";
import { siteConfig } from "@/shared/config/site";
import { createRequestTimingId, logServerTiming, timeServerAsync } from "@/shared/lib/server-timing";

const fetchCurrentUser = cache(async (token: string): Promise<BackofficeUser | null> => {
  const requestId = createRequestTimingId("backoffice-current-user");
  let response: Response;
  try {
    response = await timeServerAsync(
      "backoffice.current_user.fetch",
      () =>
        fetch(`${siteConfig.apiBaseUrl}/users/auth/current-user/`, {
          method: "GET",
          headers: {
            Authorization: `Token ${token}`,
            "X-Request-ID": requestId,
          },
          cache: "no-store",
          credentials: "omit",
        }),
      { request_id: requestId },
    );
  } catch {
    return null;
  }

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as BackofficeUser;
});

export async function requireBackofficeAccess(
  locale: string,
  requiredCapability: BackofficeCapabilityCode | BackofficeCapabilityCode[] = "backoffice.access",
): Promise<{ user: BackofficeUser; token: string }> {
  const requestId = createRequestTimingId("backoffice-auth");
  const startedAt = performance.now();
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_TOKEN_COOKIE_KEY)?.value;

  if (!token) {
    redirect(`/${locale}/login?next=/${locale}/backoffice`);
  }

  const user = await fetchCurrentUser(token);
  if (!user || !user.has_backoffice_access) {
    redirect(`/${locale}/`);
  }

  if (!hasBackofficeCapabilities(user, requiredCapability)) {
    redirect(`/${locale}/backoffice`);
  }

  logServerTiming("backoffice.require_access", startedAt, {
    locale,
    request_id: requestId,
    required_capability: Array.isArray(requiredCapability) ? requiredCapability.join(",") : requiredCapability,
  });

  return { user, token };
}
