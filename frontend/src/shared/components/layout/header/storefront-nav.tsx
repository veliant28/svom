"use client";

import { CircleCheckBig, ShoppingCart } from "lucide-react";
import { useTranslations } from "next-intl";

import { useCart } from "@/features/cart/hooks/use-cart";
import { GarageHeaderControl } from "@/features/garage/components/header/garage-header-control";
import { SearchHeaderControl } from "@/features/search/components/header/search-header-control";
import { usePathname } from "@/i18n/navigation";
import { HeaderParentCategoryButtons } from "@/shared/components/layout/header/categories/header-parent-category-buttons";
import { HeaderIconLink } from "@/shared/components/layout/header/header-icon-control";

function isActivePath(pathname: string, target: string): boolean {
  if (target === "/") {
    return pathname === "/";
  }
  return pathname === target || pathname.startsWith(`${target}/`);
}

type StorefrontNavProps = {
  showCategories?: boolean;
};

export function StorefrontNav({ showCategories = true }: StorefrontNavProps) {
  const t = useTranslations("common.header");
  const pathname = usePathname();
  const { itemsCount } = useCart();
  const hasCartItems = itemsCount > 0;

  return (
    <nav className="flex items-center gap-2">
      {showCategories ? <HeaderParentCategoryButtons /> : null}
      <SearchHeaderControl />
      <GarageHeaderControl />
      <HeaderIconLink
        href="/cart"
        tooltip={t("tooltips.cart")}
        icon={hasCartItems ? <CircleCheckBig size={18} /> : <ShoppingCart size={18} />}
        isActive={isActivePath(pathname, "/cart") || isActivePath(pathname, "/checkout")}
        badge={itemsCount}
        className={`header-control-cart ${hasCartItems ? "header-control-cart-active" : ""}`.trim()}
      />
    </nav>
  );
}
