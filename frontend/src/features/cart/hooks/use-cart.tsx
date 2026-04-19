"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { addToCart } from "@/features/cart/api/add-to-cart";
import { getCart } from "@/features/cart/api/get-cart";
import { removeCartItem } from "@/features/cart/api/remove-cart-item";
import { updateCartItem } from "@/features/cart/api/update-cart-item";
import type { Cart, CartItem } from "@/features/commerce/types";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type CartContextValue = {
  cart: Cart | null;
  isLoading: boolean;
  itemsCount: number;
  isProductInCart: (productId: string) => boolean;
  getProductQuantity: (productId: string) => number;
  setProductQuantity: (productId: string, quantity: number, maxQuantity?: number | null) => Promise<void>;
  refresh: () => Promise<void>;
  addProduct: (productId: string, quantity?: number) => Promise<void>;
  updateItemQuantity: (itemId: string, quantity: number) => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
};

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const { token, isAuthenticated } = useAuth();
  const t = useTranslations("commerce.cart.messages");
  const { showApiError, showSuccess } = useStorefrontFeedback();
  const [cart, setCart] = useState<Cart | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setCart(null);
      return;
    }

    setIsLoading(true);
    try {
      const data = await getCart(token);
      setCart(data);
    } catch (error) {
      setCart(null);
      showApiError(error, t("loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }, [token, isAuthenticated, showApiError, t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const addProduct = useCallback(
    async (productId: string, quantity = 1) => {
      if (!token || !isAuthenticated) {
        return;
      }

      try {
        const updated = await addToCart(token, productId, quantity);
        setCart(updated);
        showSuccess(t("added"));
      } catch (error) {
        showApiError(error, t("actionFailed"));
      }
    },
    [isAuthenticated, showApiError, showSuccess, t, token],
  );

  const updateItemQuantity = useCallback(
    async (itemId: string, quantity: number) => {
      if (!token || !isAuthenticated) {
        return;
      }

      try {
        const updated = await updateCartItem(token, itemId, quantity);
        setCart(updated);
        showSuccess(t("quantityUpdated"));
      } catch (error) {
        showApiError(error, t("actionFailed"));
      }
    },
    [isAuthenticated, showApiError, showSuccess, t, token],
  );

  const removeItem = useCallback(
    async (itemId: string) => {
      if (!token || !isAuthenticated) {
        return;
      }

      try {
        const updated = await removeCartItem(token, itemId);
        setCart(updated);
        showSuccess(t("removed"));
      } catch (error) {
        showApiError(error, t("actionFailed"));
      }
    },
    [isAuthenticated, showApiError, showSuccess, t, token],
  );

  const cartProductIds = useMemo(
    () => new Set((cart?.items ?? []).map((item) => item.product.id)),
    [cart?.items],
  );

  const cartItemsByProductId = useMemo(() => {
    return new Map<string, CartItem>((cart?.items ?? []).map((item) => [item.product.id, item]));
  }, [cart?.items]);

  const isProductInCart = useCallback(
    (productId: string) => cartProductIds.has(productId),
    [cartProductIds],
  );

  const getProductQuantity = useCallback(
    (productId: string) => cartItemsByProductId.get(productId)?.quantity ?? 0,
    [cartItemsByProductId],
  );

  const setProductQuantity = useCallback(
    async (productId: string, quantity: number, maxQuantity: number | null = null) => {
      if (!token || !isAuthenticated) {
        return;
      }

      const normalizedMax = typeof maxQuantity === "number" && Number.isFinite(maxQuantity) ? Math.max(0, Math.floor(maxQuantity)) : null;
      const requestedQuantity = Math.max(0, Math.floor(quantity));
      const nextQuantity = normalizedMax === null ? requestedQuantity : Math.min(requestedQuantity, normalizedMax);
      const existingItem = cartItemsByProductId.get(productId);

      if (nextQuantity <= 0) {
        if (existingItem) {
          await removeItem(existingItem.id);
        }
        return;
      }

      if (existingItem) {
        await updateItemQuantity(existingItem.id, nextQuantity);
        return;
      }

      await addProduct(productId, nextQuantity);
    },
    [token, isAuthenticated, cartItemsByProductId, removeItem, updateItemQuantity, addProduct],
  );

  const value = useMemo<CartContextValue>(
    () => ({
      cart,
      isLoading,
      itemsCount: cart?.summary?.items_count ?? 0,
      isProductInCart,
      getProductQuantity,
      setProductQuantity,
      refresh,
      addProduct,
      updateItemQuantity,
      removeItem,
    }),
    [cart, isLoading, isProductInCart, getProductQuantity, setProductQuantity, refresh, addProduct, updateItemQuantity, removeItem],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useCart must be used within CartProvider");
  }
  return context;
}
