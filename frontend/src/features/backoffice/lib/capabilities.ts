import type { BackofficeCapabilityCode, BackofficeUser } from "@/features/backoffice/types/shared.types";
export type { BackofficeCapabilityCode } from "@/features/backoffice/types/shared.types";

export const BACKOFFICE_CAPABILITIES = {
  backofficeAccess: "backoffice.access",
  usersView: "users.view",
  usersManage: "users.manage",
  usersCardEditAdministrator: "users.card.edit.administrator",
  usersCardEditManager: "users.card.edit.manager",
  usersCardEditAll: "users.card.edit.all",
  groupsView: "groups.view",
  groupsManage: "groups.manage",
  catalogView: "catalog.view",
  catalogManage: "catalog.manage",
  ordersView: "orders.view",
  ordersManage: "orders.manage",
  customersSupport: "customers.support",
  pricingView: "pricing.view",
  pricingManage: "pricing.manage",
  suppliersView: "suppliers.view",
  suppliersManage: "suppliers.manage",
  importsView: "imports.view",
  importsManage: "imports.manage",
  schedulesView: "schedules.view",
  brandsView: "brands.view",
  categoriesView: "categories.view",
  autocatalogView: "autocatalog.view",
  paymentsView: "payments.view",
  novaPoshtaSettings: "nova_poshta.settings",
  settingsManage: "settings.manage",
  footerSettings: "footer.settings",
  promoBannersManage: "promo_banners.manage",
  loyaltyIssue: "loyalty.issue",
  procurementManage: "procurement.manage",
} as const;

export function hasBackofficeCapability(user: BackofficeUser | null | undefined, capability: BackofficeCapabilityCode): boolean {
  if (!user) {
    return false;
  }
  if (user.is_superuser) {
    return true;
  }
  if (user.backoffice_capabilities_map && user.backoffice_capabilities_map[capability]) {
    return true;
  }
  return Array.isArray(user.backoffice_capabilities) && user.backoffice_capabilities.includes(capability);
}

export function hasBackofficeCapabilities(
  user: BackofficeUser | null | undefined,
  required: BackofficeCapabilityCode | BackofficeCapabilityCode[],
): boolean {
  const list = Array.isArray(required) ? required : [required];
  return list.every((capability) => hasBackofficeCapability(user, capability));
}

export function canEditBackofficeUserCard(user: BackofficeUser | null | undefined): boolean {
  if (!user) {
    return false;
  }

  if (hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.usersManage)) {
    return true;
  }
  if (hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.usersCardEditAll)) {
    return true;
  }
  if (
    user.system_role === "administrator"
    && hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.usersCardEditAdministrator)
  ) {
    return true;
  }
  if (
    user.system_role === "manager"
    && hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.usersCardEditManager)
  ) {
    return true;
  }

  return false;
}
