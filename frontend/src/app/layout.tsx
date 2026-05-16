import "./globals.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ThemeProvider } from "@/shared/components/theme/theme-provider";

export const metadata: Metadata = {
  title: "SVOM",
  description: "SVOM autoparts catalog",
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
    shortcut: ["/icon.svg"],
    apple: [{ url: "/icon.svg" }],
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="uk" suppressHydrationWarning>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
