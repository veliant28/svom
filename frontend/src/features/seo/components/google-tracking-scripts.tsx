"use client";

import Script from "next/script";

import type { SeoPublicGoogleSettings } from "@/features/seo/types";

function normalizeId(value: string): string {
  return String(value || "").trim();
}

export function GoogleTrackingScripts({ settings }: { settings: SeoPublicGoogleSettings | null | undefined }) {
  if (!settings || !settings.is_enabled) {
    return null;
  }

  const gtmId = normalizeId(settings.gtm_container_id);
  const ga4Id = normalizeId(settings.ga4_measurement_id);
  const useGtm = gtmId.startsWith("GTM-");
  const useGa4 = !useGtm && ga4Id.startsWith("G-");

  return (
    <>
      {useGtm ? (
        <>
          <Script
            id="svom-gtm-bootstrap"
            strategy="afterInteractive"
            dangerouslySetInnerHTML={{
              __html: `
                window.dataLayer = window.dataLayer || [];
                (function(w,d,s,l,i){
                  w[l]=w[l]||[];
                  w[l].push({'gtm.start': new Date().getTime(), event:'gtm.js'});
                  var f=d.getElementsByTagName(s)[0], j=d.createElement(s), dl=l!='dataLayer'?'&l='+l:'';
                  j.async=true;
                  j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;
                  f.parentNode.insertBefore(j,f);
                })(window,document,'script','dataLayer','${gtmId}');
              `,
            }}
          />
        </>
      ) : null}

      {useGa4 ? (
        <>
          <Script
            id="svom-ga4-src"
            strategy="afterInteractive"
            src={`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(ga4Id)}`}
          />
          <Script
            id="svom-ga4-bootstrap"
            strategy="afterInteractive"
            dangerouslySetInnerHTML={{
              __html: `
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                ${settings.consent_mode_enabled ? "gtag('consent', 'default', { ad_storage: 'denied', analytics_storage: 'granted' });" : ""}
                gtag('config', '${ga4Id}', {
                  anonymize_ip: ${settings.anonymize_ip ? "true" : "false"},
                  debug_mode: ${settings.debug_mode ? "true" : "false"}
                });
              `,
            }}
          />
        </>
      ) : null}
    </>
  );
}
