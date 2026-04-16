export type AuthUser = {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  preferred_language: "uk" | "ru" | "en";
  is_staff: boolean;
  is_superuser: boolean;
};

export type LoginResponse = {
  token: string;
  user: AuthUser;
};
