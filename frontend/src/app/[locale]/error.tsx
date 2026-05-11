"use client";

import { useEffect } from "react";

export default function LocaleError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Locale route error:", error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-[60vh] w-full max-w-3xl items-center px-4 py-12">
      <section
        className="w-full rounded-xl border p-6"
        style={{
          borderColor: "var(--border)",
          backgroundColor: "var(--surface)",
          color: "var(--text)",
        }}
      >
        <h1 className="text-2xl font-semibold">Page couldn&apos;t load</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
          The server had a temporary problem. Please retry.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded-md border px-3 py-2 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => reset()}
          >
            Retry
          </button>
          <button
            type="button"
            className="rounded-md border px-3 py-2 text-sm"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => window.location.reload()}
          >
            Hard reload
          </button>
        </div>
      </section>
    </main>
  );
}
