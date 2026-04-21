import type { BackofficeCapabilityCode } from "@/features/backoffice/types/shared.types";

export type AuthUser = {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  middle_name: string;
  phone: string;
  preferred_language: "uk" | "ru" | "en";
  is_staff: boolean;
  is_superuser: boolean;
  groups: Array<{ id: number; name: string }>;
  system_role: "administrator" | "manager" | "user" | "operator" | null;
  backoffice_capabilities: BackofficeCapabilityCode[];
  backoffice_capabilities_map: Record<string, boolean>;
  has_backoffice_access: boolean;
};

export type LoginResponse = {
  token: string;
  user: AuthUser;
};
