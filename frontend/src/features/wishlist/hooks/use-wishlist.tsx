"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import type { WishlistItem } from "@/features/commerce/types";
import { addWishlistItem } from "@/features/wishlist/api/add-wishlist-item";
import { getWishlist } from "@/features/wishlist/api/get-wishlist";
import { removeWishlistItem } from "@/features/wishlist/api/remove-wishlist-item";
import { useStorefrontFeedback } from "@/shared/hooks/use-storefront-feedback";

type WishlistContextValue = {
  items: WishlistItem[];
  isLoading: boolean;
  refresh: () => Promise<void>;
  isInWishlist: (productId: string) => boolean;
  toggleWishlist: (productId: string) => Promise<void>;
};

const WishlistContext = createContext<WishlistContextValue | null>(null);

export function WishlistProvider({ children }: { children: React.ReactNode }) {
  const { token, isAuthenticated } = useAuth();
  const t = useTranslations("commerce.wishlist.messages");
  const { showApiError, showSuccess } = useStorefrontFeedback();
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setItems([]);
      return;
    }

    setIsLoading(true);
    try {
      const data = await getWishlist(token);
      setItems(Array.isArray(data) ? data : []);
    } catch (error) {
      setItems([]);
      showApiError(error, t("loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, showApiError, t, token]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const isInWishlist = useCallback(
    (productId: string) => items.some((item) => item.product.id === productId),
    [items],
  );

  const toggleWishlist = useCallback(
    async (productId: string) => {
      if (!token || !isAuthenticated) {
        return;
      }

      const existingItem = items.find((item) => item.product.id === productId);
      try {
        if (existingItem) {
          await removeWishlistItem(token, existingItem.id);
          setItems((prev) => prev.filter((item) => item.id !== existingItem.id));
          showSuccess(t("removed"));
          return;
        }

        const created = await addWishlistItem(token, productId);
        setItems((prev) => [created, ...prev.filter((item) => item.product.id !== productId)]);
        showSuccess(t("added"));
      } catch (error) {
        showApiError(error, t("actionFailed"));
      }
    },
    [isAuthenticated, items, showApiError, showSuccess, t, token],
  );

  const value = useMemo(
    () => ({
      items,
      isLoading,
      refresh,
      isInWishlist,
      toggleWishlist,
    }),
    [items, isLoading, refresh, isInWishlist, toggleWishlist],
  );

  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>;
}

export function useWishlist() {
  const context = useContext(WishlistContext);
  if (!context) {
    throw new Error("useWishlist must be used within WishlistProvider");
  }
  return context;
}
