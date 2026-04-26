"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";

import { useFooterSettings } from "@/features/marketing/hooks/use-footer-settings";

export function HeaderContactSticker() {
  const t = useTranslations("common");
  const { settings } = useFooterSettings();

  const workingHoursValue = (settings?.working_hours || "").trim() || t("footer.workingHoursValue");
  const phoneValue = (settings?.phone || "").trim() || t("footer.phoneValue");
  const phoneHref = `tel:${phoneValue.replace(/[^\d+]/g, "")}`;

  return (
    <div className="header-contact-sticker-anchor hidden xl:flex">
      <a href={phoneHref} className="header-contact-sticker" aria-label={`${t("footer.phone")}: ${phoneValue}`}>
        <Image
          src="/images/header-note-sticker.png"
          alt=""
          aria-hidden
          width={994}
          height={870}
          priority
          loading="eager"
          className="header-contact-sticker-art"
        />
        <span className="header-contact-sticker-overlay">
          <span className="header-contact-sticker-item">
            <span className="header-contact-sticker-label">{t("footer.workingHours")}:</span>
            <span className="header-contact-sticker-value">{workingHoursValue}</span>
          </span>
          <span className="header-contact-sticker-item">
            <span className="header-contact-sticker-label">{t("footer.phone")}:</span>
            <span className="header-contact-sticker-value">{phoneValue}</span>
          </span>
        </span>
      </a>
    </div>
  );
}
