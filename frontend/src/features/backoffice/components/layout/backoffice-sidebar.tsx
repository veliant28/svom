"use client";

import type { ComponentType } from "react";
import {
  Car,
  CircleDollarSign,
  ShieldCheck,
  LayoutDashboard,
  Package,
  UsersRound,
  Shapes,
  ShoppingBag,
  PackageCheck,
  TicketPercent,
  Tags,
  Truck,
  Wallet2,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { RoleGroupBadge } from "@/features/backoffice/components/rbac/role-group-badge";
import { BACKOFFICE_CAPABILITIES, hasBackofficeCapabilities, type BackofficeCapabilityCode } from "@/features/backoffice/lib/capabilities";
import type { BackofficeUser } from "@/features/backoffice/types/backoffice";
import { Link, usePathname } from "@/i18n/navigation";

type SidebarNavItem = {
  href: string;
  icon: ComponentType<{ size?: number }>;
  key:
    | "dashboard"
    | "suppliers"
    | "products"
    | "pricing"
    | "loyalty"
    | "payments"
    | "brands"
    | "categories"
    | "autocatalog"
    | "orders"
    | "novaPoshtaSenders"
    | "users"
    | "groups";
  requiredCapability: BackofficeCapabilityCode | BackofficeCapabilityCode[];
};

const NAV_ITEMS: SidebarNavItem[] = [
  { href: "/backoffice", icon: LayoutDashboard, key: "dashboard", requiredCapability: BACKOFFICE_CAPABILITIES.backofficeAccess },
  { href: "/backoffice/users", icon: UsersRound, key: "users", requiredCapability: BACKOFFICE_CAPABILITIES.usersView },
  { href: "/backoffice/groups", icon: ShieldCheck, key: "groups", requiredCapability: BACKOFFICE_CAPABILITIES.groupsView },
  { href: "/backoffice/suppliers", icon: Truck, key: "suppliers", requiredCapability: BACKOFFICE_CAPABILITIES.suppliersView },
  { href: "/backoffice/products", icon: Package, key: "products", requiredCapability: BACKOFFICE_CAPABILITIES.catalogView },
  { href: "/backoffice/pricing", icon: CircleDollarSign, key: "pricing", requiredCapability: BACKOFFICE_CAPABILITIES.pricingView },
  { href: "/backoffice/loyalty", icon: TicketPercent, key: "loyalty", requiredCapability: BACKOFFICE_CAPABILITIES.loyaltyIssue },
  { href: "/backoffice/payments", icon: Wallet2, key: "payments", requiredCapability: BACKOFFICE_CAPABILITIES.settingsManage },
  { href: "/backoffice/brands", icon: Tags, key: "brands", requiredCapability: BACKOFFICE_CAPABILITIES.catalogView },
  { href: "/backoffice/categories", icon: Shapes, key: "categories", requiredCapability: BACKOFFICE_CAPABILITIES.catalogView },
  { href: "/backoffice/autocatalog", icon: Car, key: "autocatalog", requiredCapability: BACKOFFICE_CAPABILITIES.catalogView },
  { href: "/backoffice/orders", icon: ShoppingBag, key: "orders", requiredCapability: BACKOFFICE_CAPABILITIES.ordersView },
  {
    href: "/backoffice/nova-poshta-senders",
    icon: PackageCheck,
    key: "novaPoshtaSenders",
    requiredCapability: [BACKOFFICE_CAPABILITIES.ordersManage, BACKOFFICE_CAPABILITIES.customersSupport],
  },
];

function normalizePath(path: string): string {
  if (!path) {
    return "/";
  }
  if (path.length > 1 && path.endsWith("/")) {
    return path.slice(0, -1);
  }
  return path;
}

function isActiveNavItem(pathname: string, href: string): boolean {
  const current = normalizePath(pathname);
  const target = normalizePath(href);

  if (target === "/backoffice") {
    return current === target;
  }

  return current === target || current.startsWith(`${target}/`);
}

export function BackofficeSidebar({ open, onNavigate, user }: { open: boolean; onNavigate: () => void; user: BackofficeUser }) {
  const t = useTranslations("backoffice.navigation");
  const pathname = usePathname();
  const navItems = NAV_ITEMS.filter((item) => hasBackofficeCapabilities(user, item.requiredCapability));
  const displayName = user.first_name || user.email;
  const roleGroupName = user.system_role ? `Backoffice Role: ${user.system_role}` : (user.groups[0]?.name || "");

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 w-72 border-r px-4 py-5 transition-transform lg:static lg:translate-x-0 ${
        open ? "translate-x-0" : "-translate-x-full"
      }`}
      style={{
        borderColor: "var(--border)",
        background: "linear-gradient(170deg, #12212c 0%, #0d1620 100%)",
        color: "#f8fbff",
      }}
    >
      <div className="mb-7 border-b pb-4" style={{ borderColor: "rgba(255,255,255,0.14)" }}>
        <div className="grid grid-cols-[minmax(0,1fr)_auto] grid-rows-2 items-center gap-x-3 gap-y-1">
          <Link
            href="/"
            onClick={onNavigate}
            className="text-xs uppercase tracking-[0.22em] text-slate-300 transition hover:text-white"
          >
            {t("brand")}
          </Link>
          <div className="justify-self-end">
            {roleGroupName ? <RoleGroupBadge groupName={roleGroupName} forceDark /> : null}
          </div>
          <h1 className="text-lg font-semibold">{t("title")}</h1>
          <p className="max-w-[11rem] truncate text-sm font-semibold text-white justify-self-end">{displayName}</p>
        </div>
      </div>

      <nav className="grid gap-1">
        {navItems.map((item) => {
          const isActive = isActiveNavItem(pathname, item.href);
          const Icon = item.icon;
          const itemClassName = `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? "font-semibold" : "font-medium"}`;
          const itemStyle = {
            backgroundColor: isActive ? "rgba(255,255,255,0.18)" : "transparent",
            color: "#f8fbff",
          };

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={itemClassName}
              style={itemStyle}
            >
              <Icon size={16} />
              <span>{t(item.key)}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
