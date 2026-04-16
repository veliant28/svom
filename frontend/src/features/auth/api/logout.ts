import { postJson } from "@/shared/api/http-client";

export async function logout(token: string): Promise<void> {
  await postJson<void, Record<string, never>>("/users/auth/logout/", {}, undefined, { token });
}
