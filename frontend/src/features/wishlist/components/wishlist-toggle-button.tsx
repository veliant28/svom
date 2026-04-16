"use client";

import { Heart } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useWishlist } from "@/features/wishlist/hooks/use-wishlist";

export function WishlistToggleButton({ productId }: { productId: string }) {
  const t = useTranslations("commerce.wishlist");
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const { isInWishlist, toggleWishlist } = useWishlist();

  const active = isInWishlist(productId);

  return (
    <button
      type="button"
      className="inline-flex h-8 items-center justify-center rounded-md border px-2 text-xs"
      style={{
        borderColor: "var(--border)",
        color: active ? "var(--danger, #b42318)" : "var(--muted)",
        backgroundColor: "var(--surface)",
      }}
      onClick={async () => {
        if (!isAuthenticated) {
          router.push("/login");
          return;
        }
        await toggleWishlist(productId);
      }}
      title={active ? t("actions.remove") : t("actions.add")}
    >
      <Heart size={14} fill={active ? "currentColor" : "none"} />
    </button>
  );
}
