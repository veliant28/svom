export default function Custom500Page() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "24px",
        fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        background: "#f8fafc",
        color: "#0f172a",
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
        <h1 style={{ margin: 0, fontSize: "22px", lineHeight: 1.2 }}>Temporary server issue</h1>
        <p style={{ marginTop: "10px", marginBottom: "0", color: "#475569" }}>
          Please reload the page in a moment.
        </p>
      </section>
    </main>
  );
}
