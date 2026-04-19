"use client";

import { CircleCheckBig, ShoppingCart } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useCart } from "@/features/cart/hooks/use-cart";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function AddToCartButton({
  productId,
  variant = "default",
  maxQuantity = null,
}: {
  productId: string;
  variant?: "default" | "headerGreenIcon" | "headerGreenIconLg";
  maxQuantity?: number | null;
}) {
  const t = useTranslations("commerce.cart");
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const { showInfo } = useStorefrontFeedback();
  const { addProduct, isProductInCart, getProductQuantity } = useCart();
  const iconOnly = variant === "headerGreenIcon" || variant === "headerGreenIconLg";
  const isLargeHeaderSize = variant === "headerGreenIconLg";
  const isInCart = isProductInCart(productId);
  const currentQuantity = getProductQuantity(productId);
  const normalizedMax = typeof maxQuantity === "number" && Number.isFinite(maxQuantity) ? Math.max(0, Math.floor(maxQuantity)) : null;
  const canAddMore = normalizedMax === null || currentQuantity < normalizedMax;
  const className = iconOnly
    ? `inline-flex ${isLargeHeaderSize ? "h-10 w-10 rounded-md" : "h-8 w-8 rounded-md"} items-center justify-center border text-[#f7fffa] transition-colors disabled:opacity-60 ${isInCart ? "border-[#356f49] bg-[#3f8258]" : "border-[#3f8a5a] bg-[#4b9264]"} hover:border-[#356f49] hover:bg-[#3f8258]`
    : "inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs disabled:opacity-60";
  const style = iconOnly
    ? undefined
    : { borderColor: "var(--border)", backgroundColor: "var(--surface)" };
  const iconSize = isLargeHeaderSize ? 18 : 13;

  return (
    <span className={iconOnly ? "group relative inline-flex" : "inline-flex"}>
      <button
        type="button"
        aria-label={t("actions.add")}
        className={className}
        style={style}
        data-in-cart={isInCart ? "true" : "false"}
        disabled={!canAddMore}
        onClick={async () => {
          if (!canAddMore) {
            return;
          }
          if (!isAuthenticated) {
            showInfo(t("messages.authRequiredAction"));
            router.push("/login");
            return;
          }
          await addProduct(productId, 1);
        }}
      >
        {isInCart ? (
          <CircleCheckBig size={iconSize} strokeWidth={iconOnly ? 1.9 : 2} />
        ) : (
          <ShoppingCart size={iconSize} strokeWidth={iconOnly ? 1.9 : 2} />
        )}
        {iconOnly ? null : t("actions.add")}
      </button>
      {iconOnly ? (
        <span role="tooltip" className="header-tooltip hidden group-hover:block">
          {t("actions.add")}
        </span>
      ) : null}
    </span>
  );
}
