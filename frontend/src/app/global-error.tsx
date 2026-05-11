"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global app error:", error);
  }, [error]);

  return (
    <html>
      <body>
        <main
          style={{
            minHeight: "100vh",
            display: "grid",
            placeItems: "center",
            fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
            background: "#f8fafc",
            color: "#0f172a",
            padding: "24px",
          }}
        >
          <section
            style={{
              width: "100%",
              maxWidth: "520px",
              border: "1px solid #cbd5e1",
              borderRadius: "14px",
              background: "#ffffff",
              padding: "24px",
              boxShadow: "0 10px 24px rgba(15, 23, 42, 0.08)",
            }}
          >
            <h1 style={{ margin: 0, fontSize: "22px", lineHeight: 1.2 }}>Page failed to load</h1>
            <p style={{ marginTop: "10px", marginBottom: "16px", color: "#475569" }}>
              Temporary server/API outage detected. Try again.
            </p>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={reset}
                style={{
                  border: "1px solid #94a3b8",
                  borderRadius: "10px",
                  background: "#ffffff",
                  color: "#0f172a",
                  padding: "10px 14px",
                  cursor: "pointer",
                }}
              >
                Retry
              </button>
              <button
                type="button"
                onClick={() => window.location.reload()}
                style={{
                  border: "1px solid #0f172a",
                  borderRadius: "10px",
                  background: "#0f172a",
                  color: "#ffffff",
                  padding: "10px 14px",
                  cursor: "pointer",
                }}
              >
                Hard reload
              </button>
            </div>
          </section>
        </main>
      </body>
    </html>
  );
}
