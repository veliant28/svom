"use client";

import type { ComponentType } from "react";
import {
  Activity,
  Car,
  CircleDollarSign,
  LayoutDashboard,
  Package,
  Shapes,
  ShoppingBag,
  PackageCheck,
  Tags,
  Truck,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";

type SidebarNavItem = {
  href: string;
  icon: ComponentType<{ size?: number }>;
  key:
    | "dashboard"
    | "suppliers"
    | "products"
    | "pricing"
    | "brands"
    | "categories"
    | "autocatalog"
    | "matching"
    | "orders"
    | "novaPoshtaSenders";
};

const NAV_ITEMS: SidebarNavItem[] = [
  { href: "/backoffice", icon: LayoutDashboard, key: "dashboard" },
  { href: "/backoffice/suppliers", icon: Truck, key: "suppliers" },
  { href: "/backoffice/products", icon: Package, key: "products" },
  { href: "/backoffice/pricing", icon: CircleDollarSign, key: "pricing" },
  { href: "/backoffice/brands", icon: Tags, key: "brands" },
  { href: "/backoffice/categories", icon: Shapes, key: "categories" },
  { href: "/backoffice/autocatalog", icon: Car, key: "autocatalog" },
  { href: "/backoffice/matching", icon: Activity, key: "matching" },
  { href: "/backoffice/orders", icon: ShoppingBag, key: "orders" },
  { href: "/backoffice/nova-poshta-senders", icon: PackageCheck, key: "novaPoshtaSenders" },
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

export function BackofficeSidebar({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  const t = useTranslations("backoffice.navigation");
  const pathname = usePathname();

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
        <Link
          href="/"
          onClick={onNavigate}
          className="text-xs uppercase tracking-[0.22em] text-slate-300 transition hover:text-white"
        >
          {t("brand")}
        </Link>
        <h1 className="mt-1 text-lg font-semibold">{t("title")}</h1>
      </div>

      <nav className="grid gap-1">
        {NAV_ITEMS.map((item) => {
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
