import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["uk", "ru", "en"],
  defaultLocale: "uk",
  localePrefix: "always",
});

export type AppLocale = (typeof routing.locales)[number];
