import { patchJson } from "@/shared/api/http-client";

import type { AuthUser } from "@/features/auth/types/auth";

export type UpdateProfilePayload = Partial<
  Pick<AuthUser, "email" | "username" | "first_name" | "last_name" | "phone" | "preferred_language">
>;

export async function updateProfile(token: string, payload: UpdateProfilePayload): Promise<AuthUser> {
  return patchJson<AuthUser, UpdateProfilePayload>("/users/auth/profile/", payload, undefined, { token });
}
