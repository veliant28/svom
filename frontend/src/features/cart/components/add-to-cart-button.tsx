"use client";

import { ShoppingCart } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useCart } from "@/features/cart/hooks/use-cart";

export function AddToCartButton({ productId }: { productId: string }) {
  const t = useTranslations("commerce.cart");
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const { addProduct } = useCart();

  return (
    <button
      type="button"
      className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      onClick={async () => {
        if (!isAuthenticated) {
          router.push("/login");
          return;
        }
        await addProduct(productId, 1);
      }}
    >
      <ShoppingCart size={13} />
      {t("actions.add")}
    </button>
  );
}
