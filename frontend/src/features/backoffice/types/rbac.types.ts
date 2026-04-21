import type { BackofficeCapabilityCode, BackofficeSystemRole, BackofficeUserGroup } from "@/features/backoffice/types/shared.types";

export type BackofficeCapabilityDefinition = {
  code: BackofficeCapabilityCode;
  title: string;
  description: string;
};

export type BackofficeRoleDefinition = {
  code: NonNullable<BackofficeSystemRole>;
  title: string;
  description: string;
  group_name: string;
  capabilities: BackofficeCapabilityCode[];
};

export type BackofficeRbacMeta = {
  roles: BackofficeRoleDefinition[];
  capabilities: BackofficeCapabilityDefinition[];
};

export type BackofficeManagedUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  middle_name: string;
  phone: string;
  preferred_language: "uk" | "ru" | "en";
  is_active: boolean;
  full_name: string;
  groups: BackofficeUserGroup[];
  system_role: BackofficeSystemRole;
  has_backoffice_access: boolean;
};

export type BackofficeManagedUserDetail = BackofficeManagedUser & {
  username: string;
  is_staff: boolean;
  is_superuser: boolean;
  capabilities: BackofficeCapabilityCode[];
};

export type BackofficeManagedUserWritePayload = Partial<{
  email: string;
  first_name: string;
  last_name: string;
  middle_name: string;
  phone: string;
  preferred_language: "uk" | "ru" | "en";
  is_active: boolean;
  password: string;
  group_ids: number[];
  system_role: NonNullable<BackofficeSystemRole> | null;
}>;

export type BackofficeGroupItem = {
  id: number;
  name: string;
  members_count: number;
  capability_codes: BackofficeCapabilityCode[];
  is_system_role_group: boolean;
  system_role: BackofficeSystemRole;
};

export type BackofficeGroupWritePayload = Partial<{
  name: string;
  capability_codes: BackofficeCapabilityCode[];
}>;
