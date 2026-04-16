"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import type { PromoBanner } from "@/features/marketing/types";

type PromoBannerCarouselProps = {
  banners: PromoBanner[];
  intervalMs?: number;
};

export function PromoBannerCarousel({ banners, intervalMs = 4500 }: PromoBannerCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (banners.length <= 1) {
      return;
    }

    const timer = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % banners.length);
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [banners.length, intervalMs]);

  if (banners.length === 0) {
    return null;
  }

  const activeBanner = banners[activeIndex];

  return (
    <section className="mx-auto mt-6 max-w-6xl px-4">
      <div className="relative overflow-hidden rounded-2xl border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <div className="grid gap-4 p-4 md:grid-cols-[1.3fr_1fr] md:p-6">
          <div
            className="min-h-[180px] rounded-xl bg-cover bg-center"
            style={{ backgroundImage: `url(${activeBanner.image_url})` }}
          />
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
