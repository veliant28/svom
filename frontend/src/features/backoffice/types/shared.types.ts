export type BackofficeCapabilityCode =
  | "backoffice.access"
  | "users.view"
  | "users.manage"
  | "users.card.edit.administrator"
  | "users.card.edit.manager"
  | "users.card.edit.all"
  | "groups.view"
  | "groups.manage"
  | "catalog.view"
  | "catalog.manage"
  | "orders.view"
  | "orders.manage"
  | "customers.support"
  | "pricing.view"
  | "pricing.manage"
  | "suppliers.view"
  | "suppliers.manage"
  | "imports.view"
  | "imports.manage"
  | "schedules.view"
  | "brands.view"
  | "categories.view"
  | "autocatalog.view"
  | "payments.view"
  | "nova_poshta.settings"
  | "settings.manage"
  | "footer.settings"
  | "promo_banners.manage"
  | "loyalty.issue"
  | "procurement.manage";

export type BackofficeSystemRole = "administrator" | "manager" | "user" | "operator" | null;

export type BackofficeUserGroup = {
  id: number;
  name: string;
};

export type BackofficeUser = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  preferred_language: "uk" | "ru" | "en";
  is_staff: boolean;
  is_superuser: boolean;
  groups: BackofficeUserGroup[];
  system_role: BackofficeSystemRole;
  backoffice_capabilities: BackofficeCapabilityCode[];
  backoffice_capabilities_map: Record<string, boolean>;
  has_backoffice_access: boolean;
};

export type BackofficeActionResponse = {
  mode: "sync" | "async";
  task_id?: string;
  run_id?: string;
  status?: string;
  result?: Record<string, unknown>;
  results?: Array<Record<string, unknown>>;
  sources?: number;
  stats?: Record<string, unknown>;
};
