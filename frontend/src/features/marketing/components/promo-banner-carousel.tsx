"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import type { PromoBanner, PromoBannerSettings } from "@/features/marketing/types";

type PromoBannerCarouselProps = {
  banners: PromoBanner[];
  settings?: PromoBannerSettings | null;
};

const BLINDS_COUNT = 12;

export function PromoBannerCarousel({ banners, settings }: PromoBannerCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const autoplayEnabled = settings?.autoplay_enabled ?? true;
  const intervalMs = Math.max(1000, Number(settings?.transition_interval_ms || 4500));
  const speedMs = Math.max(150, Number(settings?.transition_speed_ms || 700));
  const effect = settings?.transition_effect || "fade";

  useEffect(() => {
    if (activeIndex <= banners.length - 1) {
      return;
    }
    setActiveIndex(0);
  }, [activeIndex, banners.length]);

  useEffect(() => {
    if (!autoplayEnabled || banners.length <= 1) {
      return;
    }

    const timer = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % banners.length);
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [autoplayEnabled, banners.length, intervalMs]);

  if (banners.length === 0) {
    return null;
  }

  const activeBanner = banners[activeIndex];
  const imageView = (
    <div className="relative min-h-[180px] overflow-hidden rounded-xl">
      <div
        className={`absolute inset-0 bg-cover bg-center ${
          effect === "fade"
            ? "promo-banner-enter-fade"
            : effect === "slide_left"
              ? "promo-banner-enter-slide-left"
              : effect === "slide_up"
                ? "promo-banner-enter-slide-up"
                : effect === "zoom_in"
                  ? "promo-banner-enter-zoom"
                  : ""
        }`}
        key={`${activeBanner.id}-${activeIndex}-${effect}`}
        style={{
          backgroundImage: `url(${activeBanner.image_url})`,
          animationDuration: `${speedMs}ms`,
        }}
      />

      {effect === "blinds_vertical" ? (
        <div className="absolute inset-0 grid grid-cols-12 overflow-hidden" key={`${activeBanner.id}-${activeIndex}-blinds`}>
          {Array.from({ length: BLINDS_COUNT }).map((_, blindIndex) => (
            <span
              key={blindIndex}
              className="promo-banner-blind-strip"
              style={{
                backgroundImage: `url(${activeBanner.image_url})`,
                backgroundSize: `${BLINDS_COUNT * 100}% 100%`,
                backgroundPosition: `${(blindIndex / (BLINDS_COUNT - 1)) * 100}% 50%`,
                animationDuration: `${speedMs}ms`,
                animationDelay: `${Math.round((blindIndex / BLINDS_COUNT) * speedMs * 0.6)}ms`,
              }}
            />
          ))}
        </div>
      ) : null}
    </div>
  );

  return (
    <section className="mx-auto mt-6 max-w-6xl px-4">
      <div className="relative overflow-hidden rounded-2xl border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div className="grid gap-4 p-4 md:grid-cols-[1.3fr_1fr] md:p-6">
          {activeBanner.target_url ? (
            <a href={activeBanner.target_url} className="block" aria-label={activeBanner.title}>
              {imageView}
            </a>
          ) : imageView}
          <div className="flex flex-col justify-center">
            <h2 className="text-xl font-semibold md:text-2xl">{activeBanner.title}</h2>
            <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
              {activeBanner.description}
            </p>
          </div>
        </div>

        <div className="absolute bottom-3 right-3 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveIndex((current) => (current - 1 + banners.length) % banners.length)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            onClick={() => setActiveIndex((current) => (current + 1) % banners.length)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}
