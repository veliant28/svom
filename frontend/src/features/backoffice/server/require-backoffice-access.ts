import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AUTH_TOKEN_COOKIE_KEY } from "@/features/auth/lib/auth-token-constants";
import { hasBackofficeCapabilities, type BackofficeCapabilityCode } from "@/features/backoffice/lib/capabilities";
import type { BackofficeUser } from "@/features/backoffice/types/backoffice";
import { siteConfig } from "@/shared/config/site";

async function fetchCurrentUser(token: string): Promise<BackofficeUser | null> {
  let response: Response;
  try {
    response = await fetch(`${siteConfig.apiBaseUrl}/users/auth/current-user/`, {
      method: "GET",
      headers: {
        Authorization: `Token ${token}`,
      },
      cache: "no-store",
      credentials: "omit",
    });
  } catch {
    return null;
  }

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as BackofficeUser;
}

export async function requireBackofficeAccess(
  locale: string,
  requiredCapability: BackofficeCapabilityCode | BackofficeCapabilityCode[] = "backoffice.access",
): Promise<{ user: BackofficeUser; token: string }> {
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

  return { user, token };
}
