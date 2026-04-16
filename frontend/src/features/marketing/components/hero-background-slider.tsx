"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import type { HeroSlide } from "@/features/marketing/types";

type HeroBackgroundSliderProps = {
  slides: HeroSlide[];
  intervalMs?: number;
};

export function HeroBackgroundSlider({ slides, intervalMs = 5000 }: HeroBackgroundSliderProps) {
  const t = useTranslations("common.home");
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (slides.length <= 1) {
      return;
    }

    const timer = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % slides.length);
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [slides.length, intervalMs]);

  if (slides.length === 0) {
    return (
      <section className="relative min-h-[420px] overflow-hidden border-b" style={{ borderColor: "var(--border)" }}>
        <div className="absolute inset-0 bg-[linear-gradient(120deg,#1b252d,#3a4d59)]" />
        <div className="relative mx-auto flex max-w-6xl flex-col justify-end px-4 py-14 text-white">
          <h1 className="text-4xl font-bold">{t("brand")}</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-200">{t("heroPlaceholder")}</p>
        </div>
      </section>
    );
  }

  const activeSlide = slides[activeIndex];

  return (
    <section className="relative min-h-[420px] overflow-hidden border-b" style={{ borderColor: "var(--border)" }}>
      <div
        className="absolute inset-0 bg-cover bg-center transition-all duration-700"
        style={{
          backgroundImage: `linear-gradient(rgba(0,0,0,0.45), rgba(0,0,0,0.7)), url(${activeSlide.desktop_image_url})`,
        }}
      />
      <div className="relative mx-auto flex max-w-6xl flex-col justify-end px-4 py-14 text-white">
        <p className="text-xs uppercase tracking-[0.2em]">{t("performanceTagline")}</p>
        <h1 className="mt-2 max-w-3xl text-3xl font-semibold md:text-5xl">{activeSlide.title}</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-200 md:text-base">{activeSlide.subtitle}</p>
      </div>
    </section>
  );
}
