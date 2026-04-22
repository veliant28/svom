import { CatalogShowcaseSection } from "@/features/catalog/sections/catalog-showcase-section";
import { HomeMarketingSection } from "@/features/marketing/sections/home-marketing-section";

export function StorefrontHomePage() {
  return (
    <>
      <HomeMarketingSection />
      <CatalogShowcaseSection />
    </>
  );
}
