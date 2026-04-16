import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AUTH_TOKEN_COOKIE_KEY } from "@/features/auth/lib/auth-token-constants";
import type { BackofficeUser } from "@/features/backoffice/types/backoffice";
import { siteConfig } from "@/shared/config/site";

async function fetchCurrentUser(token: string): Promise<BackofficeUser | null> {
  const response = await fetch(`${siteConfig.apiBaseUrl}/users/auth/current-user/`, {
    method: "GET",
    headers: {
      Authorization: `Token ${token}`,
    },
    cache: "no-store",
    credentials: "omit",
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as BackofficeUser;
}

export async function requireBackofficeAccess(locale: string): Promise<{ user: BackofficeUser; token: string }> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_TOKEN_COOKIE_KEY)?.value;

  if (!token) {
    redirect(`/${locale}/login?next=/${locale}/backoffice`);
  }

  const user = await fetchCurrentUser(token);
  if (!user || (!user.is_staff && !user.is_superuser)) {
    redirect(`/${locale}/`);
  }

  return { user, token };
}
