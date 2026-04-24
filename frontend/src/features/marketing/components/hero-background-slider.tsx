"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import type { HeroSlide, HeroSlideEffect, HeroSlideSettings } from "@/features/marketing/types";

type HeroBackgroundSliderProps = {
  slides: HeroSlide[];
  settings?: HeroSlideSettings | null;
};

const DEFAULT_INTERVAL_MS = 5000;
const DEFAULT_SPEED_MS = 900;
const DEFAULT_EFFECT: HeroSlideEffect = "crossfade";

export function HeroBackgroundSlider({ slides, settings }: HeroBackgroundSliderProps) {
  const t = useTranslations("common.home");
  const [activeIndex, setActiveIndex] = useState(0);
  const [activeFallbackPhraseIndex, setActiveFallbackPhraseIndex] = useState(0);
  const autoplayEnabled = settings?.autoplay_enabled ?? true;
  const intervalMs = Math.max(settings?.transition_interval_ms ?? DEFAULT_INTERVAL_MS, 1000);
  const transitionSpeedMs = Math.max(settings?.transition_speed_ms ?? DEFAULT_SPEED_MS, 150);
  const transitionEffect = settings?.transition_effect ?? DEFAULT_EFFECT;
  const fallbackPhrases = [
    t("fallbackPhrasePrimary"),
    t("fallbackPhraseSecondary"),
    t("fallbackPhraseTertiary"),
  ];

  useEffect(() => {
    if (!autoplayEnabled || slides.length <= 1) {
      return;
    }

    const timer = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % slides.length);
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [autoplayEnabled, intervalMs, slides.length]);

  useEffect(() => {
    if (activeIndex <= slides.length - 1) {
      return;
    }
    setActiveIndex(0);
  }, [activeIndex, slides.length]);

  useEffect(() => {
    if (slides.length > 0 || fallbackPhrases.length <= 1) {
      return;
    }

    const timer = window.setInterval(() => {
      setActiveFallbackPhraseIndex((current) => (current + 1) % fallbackPhrases.length);
    }, 10000);

    return () => window.clearInterval(timer);
  }, [fallbackPhrases.length, slides.length]);

  if (slides.length === 0) {
    return (
      <section className="relative min-h-[420px] overflow-hidden border-b" style={{ borderColor: "var(--border)" }}>
        <div className="hero-fallback-surface absolute inset-0" />
        <div className="hero-fallback-overlay absolute inset-0" />
        <div className="hero-fallback-glow absolute inset-0" />
        <div className="relative mx-auto flex max-w-6xl flex-col justify-end px-4 py-14" style={{ color: "var(--hero-fallback-text)" }}>
          <p className="hero-performance-tagline text-xs uppercase tracking-[0.28em]">
            {t("performanceTagline")}
          </p>
          <div className="relative mt-2 min-h-[7.5rem] max-w-4xl md:min-h-[9rem]">
            {fallbackPhrases.map((phrase, index) => {
              const isActive = index === activeFallbackPhraseIndex;
              return (
                <h1
                  key={phrase}
                  className={`absolute inset-0 text-4xl font-semibold transition-all duration-[1400ms] ease-[cubic-bezier(0.22,1,0.36,1)] md:text-6xl ${
                    isActive
                      ? "translate-y-0 opacity-100"
                      : "pointer-events-none translate-y-5 opacity-0"
                  }`}
                >
                  {phrase}
                </h1>
              );
            })}
          </div>
          <p className="mt-4 max-w-2xl text-sm md:text-lg" style={{ color: "var(--hero-subtitle-text)" }}>
            {t("fallbackSlogan")}
          </p>
        </div>
      </section>
    );
  }

  const activeSlide = slides[activeIndex];

  return (
    <section className="relative min-h-[420px] overflow-hidden border-b" style={{ borderColor: "var(--border)" }}>
      <div className="hero-theme-underlay absolute inset-0" />
      {slides.map((slide, index) => {
        const isActive = index === activeIndex;
        return (
          <div
            key={slide.id}
            className={`absolute inset-0 ${isActive ? "opacity-100" : "opacity-0"} transition-opacity will-change-transform`}
            style={{ transitionDuration: `${transitionSpeedMs}ms` }}
            aria-hidden={!isActive}
          >
            <picture
              className={`hero-slide-image-layer hero-slide-effect-${transitionEffect} ${isActive ? "hero-slide-image-active" : ""}`}
              style={{ animationDuration: `${Math.max(intervalMs, transitionSpeedMs + 400)}ms` }}
            >
              <source media="(max-width: 767px)" srcSet={slide.mobile_image_url || slide.desktop_image_url} />
              <img
                src={slide.desktop_image_url}
                alt={slide.title}
                className="h-full w-full object-cover"
              />
            </picture>
          </div>
        );
      })}
      <div className="hero-theme-overlay absolute inset-0" />
      <div className="hero-theme-glow absolute inset-0" />
      <div className="relative mx-auto flex max-w-6xl flex-col justify-end px-4 py-14" style={{ color: "var(--hero-slide-text)" }}>
        <p className="hero-performance-tagline text-xs uppercase tracking-[0.28em]">
          {t("performanceTagline")}
        </p>
        <div
          key={activeSlide.id}
          className="hero-copy-enter max-w-3xl"
          style={{ animationDuration: `${Math.max(transitionSpeedMs, 350)}ms` }}
        >
          <h1 className="mt-2 text-3xl font-semibold md:text-5xl">{activeSlide.title}</h1>
          <p className="mt-3 max-w-2xl text-sm md:text-base" style={{ color: "var(--hero-subtitle-text)" }}>{activeSlide.subtitle}</p>
        </div>
      </div>
      {slides.length > 1 ? (
        <div className="pointer-events-none absolute bottom-5 left-4 right-4 mx-auto flex max-w-6xl gap-2">
          {slides.map((slide, index) => (
            <span
              key={slide.id}
              className="h-1.5 flex-1 rounded-full transition-all"
              style={{
                backgroundColor: index === activeIndex ? "rgba(255,255,255,0.88)" : "rgba(255,255,255,0.28)",
              }}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
