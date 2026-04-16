import type { ReactNode } from "react";

import { Header } from "@/shared/components/layout/header";

export default function StorefrontLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <Header />
      <main>{children}</main>
    </div>
  );
}
