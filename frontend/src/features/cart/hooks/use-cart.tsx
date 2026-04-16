"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { addToCart } from "@/features/cart/api/add-to-cart";
import { getCart } from "@/features/cart/api/get-cart";
import { removeCartItem } from "@/features/cart/api/remove-cart-item";
import { updateCartItem } from "@/features/cart/api/update-cart-item";
import type { Cart } from "@/features/commerce/types";

type CartContextValue = {
  cart: Cart | null;
  isLoading: boolean;
  itemsCount: number;
  refresh: () => Promise<void>;
  addProduct: (productId: string, quantity?: number) => Promise<void>;
  updateItemQuantity: (itemId: string, quantity: number) => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
};

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const { token, isAuthenticated } = useAuth();
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
    } catch {
      setCart(null);
    } finally {
      setIsLoading(false);
    }
  }, [token, isAuthenticated]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const addProduct = useCallback(
    async (productId: string, quantity = 1) => {
      if (!token || !isAuthenticated) {
        return;
      }
      const updated = await addToCart(token, productId, quantity);
      setCart(updated);
    },
    [token, isAuthenticated],
  );

  const updateItemQuantity = useCallback(
    async (itemId: string, quantity: number) => {
      if (!token || !isAuthenticated) {
        return;
      }
      const updated = await updateCartItem(token, itemId, quantity);
      setCart(updated);
    },
    [token, isAuthenticated],
  );

  const removeItem = useCallback(
    async (itemId: string) => {
      if (!token || !isAuthenticated) {
        return;
      }
      const updated = await removeCartItem(token, itemId);
      setCart(updated);
    },
    [token, isAuthenticated],
  );

  const value = useMemo<CartContextValue>(
    () => ({
      cart,
      isLoading,
      itemsCount: cart?.summary?.items_count ?? 0,
      refresh,
      addProduct,
      updateItemQuantity,
      removeItem,
    }),
    [cart, isLoading, refresh, addProduct, updateItemQuantity, removeItem],
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
