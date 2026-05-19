import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { AUTH_TOKEN_COOKIE_KEY } from "@/features/auth/lib/auth-token-constants";
import type { AuthUser } from "@/features/auth/types/auth";
import { siteConfig } from "@/shared/config/site";

const fetchCurrentUser = cache(async (token: string): Promise<AuthUser | null> => {
  let response: Response;
  try {
    response = await fetch(`${siteConfig.serverApiBaseUrl}/users/auth/current-user/`, {
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

  return (await response.json()) as AuthUser;
});

export async function requireReturnsEnabled(locale: string, nextPath: string): Promise<{ user: AuthUser; token: string }> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_TOKEN_COOKIE_KEY)?.value;

  if (!token) {
    redirect(`/${locale}/login?next=${nextPath}`);
  }

  const user = await fetchCurrentUser(token);
  if (!user) {
    redirect(`/${locale}/account/orders`);
  }

  if (!user.returns_enabled) {
    redirect(`/${locale}/account/orders`);
  }

  return { user, token };
}
