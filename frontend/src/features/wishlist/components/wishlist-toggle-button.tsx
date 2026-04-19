"use client";

import { Heart } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useWishlist } from "@/features/wishlist/hooks/use-wishlist";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

export function WishlistToggleButton({
  productId,
  variant = "default",
}: {
  productId: string;
  variant?: "default" | "headerIconLg";
}) {
  const t = useTranslations("commerce.wishlist");
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const { showInfo } = useStorefrontFeedback();
  const { isInWishlist, toggleWishlist } = useWishlist();

  const active = isInWishlist(productId);
  const isLargeHeaderSize = variant === "headerIconLg";
  const className = isLargeHeaderSize
    ? "inline-flex h-10 w-10 items-center justify-center rounded-md border"
    : "inline-flex h-8 items-center justify-center rounded-md border px-2 text-xs";
  const tooltipLabel = active ? t("actions.remove") : t("actions.add");

  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label={tooltipLabel}
        className={className}
        style={{
          borderColor: "var(--border)",
          color: active ? "var(--danger, #b42318)" : "var(--muted)",
          backgroundColor: "var(--surface)",
        }}
        onClick={async () => {
          if (!isAuthenticated) {
            showInfo(t("messages.authRequiredAction"));
            router.push("/login");
            return;
          }
          await toggleWishlist(productId);
        }}
      >
        <Heart size={isLargeHeaderSize ? 18 : 14} fill={active ? "currentColor" : "none"} />
      </button>
      <span role="tooltip" className="header-tooltip hidden group-hover:block">
        {tooltipLabel}
      </span>
    </span>
  );
}
