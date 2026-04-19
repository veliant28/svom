import { postJson } from "@/shared/api/http-client";

export type ChangePasswordPayload = {
  current_password: string;
  new_password: string;
};

export async function changePassword(token: string, payload: ChangePasswordPayload): Promise<void> {
  await postJson<void, ChangePasswordPayload>("/users/auth/change-password/", payload, undefined, { token });
}
