import { Send } from "lucide-react";

export function EmailTestPanel({
  testRecipient,
  isTesting,
  canTest,
  onRecipientChange,
  onTest,
  t,
}: {
  testRecipient: string;
  isTesting: boolean;
  canTest: boolean;
  onRecipientChange: (recipient: string) => void;
  onTest: () => void;
  t: (key: string) => string;
}) {
  return (
    <div className="rounded-lg border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <p className="text-sm font-semibold">{t("email.test.title")}</p>
      <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
        {t("email.test.helper")}
      </p>
      <div className="mt-3 grid gap-3">
        <label className="flex flex-col gap-1 text-xs">
          {t("email.test.recipient")}
          <input
            type="email"
            value={testRecipient}
            onChange={(event) => onRecipientChange(event.target.value)}
            className="h-10 rounded-md border px-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          />
        </label>
        <button
          type="button"
          disabled={!canTest}
          onClick={onTest}
          className="inline-flex h-10 w-fit items-center gap-2 rounded-md border px-3 text-xs font-semibold disabled:opacity-60"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        >
          <Send size={13} />
          {isTesting ? t("email.actions.testing") : t("email.actions.test")}
        </button>
      </div>
    </div>
  );
}
