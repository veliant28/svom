import { postJson } from "@/shared/api/http-client";

import type { LoginResponse } from "@/features/auth/types/auth";

type LoginPayload = {
  email: string;
  password: string;
};

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  return postJson<LoginResponse, LoginPayload>("/users/auth/login/", payload);
}
