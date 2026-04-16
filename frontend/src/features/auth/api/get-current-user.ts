import { getJson } from "@/shared/api/http-client";

import type { AuthUser } from "@/features/auth/types/auth";

export async function getCurrentUser(token: string): Promise<AuthUser> {
  return getJson<AuthUser>("/users/auth/current-user/", undefined, { token });
}
