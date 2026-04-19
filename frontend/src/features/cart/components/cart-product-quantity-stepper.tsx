"use client";

import { Minus, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useCart } from "@/features/cart/hooks/use-cart";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type CartProductQuantityStepperProps = {
  productId: string;
  size?: "sm" | "lg";
  maxQuantity?: number | null;
};

export function CartProductQuantityStepper({ productId, size = "sm", maxQuantity = null }: CartProductQuantityStepperProps) {
  const t = useTranslations("commerce.cart");
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const { showInfo } = useStorefrontFeedback();
  const { getProductQuantity, setProductQuantity } = useCart();
  const [isPending, setIsPending] = useState(false);
  const quantity = getProductQuantity(productId);
  const normalizedMax = typeof maxQuantity === "number" && Number.isFinite(maxQuantity) ? Math.max(0, Math.floor(maxQuantity)) : null;
  const isAtMax = normalizedMax !== null && quantity >= normalizedMax;

  const buttonSize = size === "lg" ? "h-8 w-8" : "h-7 w-7";
  const iconSize = size === "lg" ? "h-4 w-4" : "h-3.5 w-3.5";
  const valueSize = size === "lg" ? "h-8 min-w-[2.25rem] text-sm" : "h-7 min-w-[2rem] text-xs";

  const updateQuantity = async (next: number) => {
    if (isPending) {
      return;
    }

    if (!isAuthenticated) {
      showInfo(t("messages.authRequiredAction"));
      router.push("/login");
      return;
    }

    setIsPending(true);
    try {
      await setProductQuantity(productId, next, normalizedMax);
    } finally {
      setIsPending(false);
    }
  };

  return (
    <div
      className="inline-flex items-center rounded-full border p-1"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
    >
      <button
        type="button"
        className={`inline-flex ${buttonSize} items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50`}
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        aria-label={t("actions.remove")}
        disabled={isPending || quantity <= 0}
        onClick={() => {
          void updateQuantity(Math.max(quantity - 1, 0));
        }}
      >
        <Minus className={iconSize} />
      </button>

      <span className={`inline-flex ${valueSize} items-center justify-center px-2 font-semibold tabular-nums`}>
        {quantity}
      </span>

      <button
        type="button"
        className={`inline-flex ${buttonSize} items-center justify-center rounded-full border transition-colors hover:opacity-90 disabled:opacity-50`}
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        aria-label={t("actions.add")}
        disabled={isPending || isAtMax}
        onClick={() => {
          if (isAtMax) {
            return;
          }
          void updateQuantity(quantity + 1);
        }}
      >
        <Plus className={iconSize} />
      </button>
    </div>
  );
}
