"use client";

import { AuthProvider } from "@/features/auth/hooks/use-auth";
import { BackofficeToastProvider } from "@/features/backoffice/components/notifications/backoffice-toast-provider";
import { CartProvider } from "@/features/cart/hooks/use-cart";
import { CatalogWarmupProvider } from "@/features/catalog/hooks/use-catalog-warmup";
import { ActiveVehicleProvider } from "@/features/garage/hooks/use-active-vehicle";
import { StorefrontSupportReplyToastListener } from "@/features/support/components/storefront-support-reply-toast-listener";
import { WishlistProvider } from "@/features/wishlist/hooks/use-wishlist";

export function StorefrontProviders({ children }: { children: React.ReactNode }) {
  return (
    <BackofficeToastProvider>
      <AuthProvider>
        <StorefrontSupportReplyToastListener />
        <ActiveVehicleProvider>
          <CatalogWarmupProvider>
            <WishlistProvider>
              <CartProvider>{children}</CartProvider>
            </WishlistProvider>
          </CatalogWarmupProvider>
        </ActiveVehicleProvider>
      </AuthProvider>
    </BackofficeToastProvider>
  );
}
