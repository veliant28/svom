"use client";

import { AuthProvider } from "@/features/auth/hooks/use-auth";
import { BackofficeToastProvider } from "@/features/backoffice/components/notifications/backoffice-toast-provider";
import { CartProvider } from "@/features/cart/hooks/use-cart";
import { ActiveVehicleProvider } from "@/features/garage/hooks/use-active-vehicle";
import { WishlistProvider } from "@/features/wishlist/hooks/use-wishlist";

export function StorefrontProviders({ children }: { children: React.ReactNode }) {
  return (
    <BackofficeToastProvider>
      <AuthProvider>
        <ActiveVehicleProvider>
          <WishlistProvider>
            <CartProvider>{children}</CartProvider>
          </WishlistProvider>
        </ActiveVehicleProvider>
      </AuthProvider>
    </BackofficeToastProvider>
  );
}
