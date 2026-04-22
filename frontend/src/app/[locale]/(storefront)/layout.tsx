import type { ReactNode } from "react";

import { Footer } from "@/shared/components/layout/footer";
import { Header } from "@/shared/components/layout/header";

export default function StorefrontLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
