import { postJson } from "@/shared/api/http-client";

import type { LoginResponse } from "@/features/auth/types/auth";

export type RegisterPayload = {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone: string;
  preferred_language: "uk" | "ru" | "en";
};

export async function register(payload: RegisterPayload): Promise<LoginResponse> {
  return postJson<LoginResponse, RegisterPayload>("/users/auth/register/", payload);
}
