import { postJson } from "@/shared/api/http-client";

export type PasswordResetRequestPayload = {
  email: string;
  locale: "uk" | "ru" | "en";
};

export type PasswordResetConfirmPayload = {
  uid: string;
  token: string;
  new_password: string;
};

export async function requestPasswordReset(payload: PasswordResetRequestPayload): Promise<void> {
  await postJson<void, PasswordResetRequestPayload>("/users/auth/password-reset/", payload);
}

export async function confirmPasswordReset(payload: PasswordResetConfirmPayload): Promise<void> {
  await postJson<void, PasswordResetConfirmPayload>("/users/auth/password-reset/confirm/", payload);
}
