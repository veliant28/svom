import { useTranslations } from "next-intl";

import { CatalogShowcaseSection } from "@/features/catalog/sections/catalog-showcase-section";
import { HomeMarketingSection } from "@/features/marketing/sections/home-marketing-section";

export function StorefrontHomePage() {
  const t = useTranslations("common.home");

  return (
    <>
      <HomeMarketingSection />
      <section className="mx-auto max-w-6xl px-4 pt-8">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          {t("subtitle")}
        </p>
      </section>
      <CatalogShowcaseSection />
    </>
  );
}
