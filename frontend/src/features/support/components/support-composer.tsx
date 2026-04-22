"use client";

import { useState } from "react";

export function SupportComposer({
  disabled,
  isSending,
  placeholder,
  sendLabel,
  sendingLabel,
  onTypingStart,
  onTypingStop,
  onSend,
}: {
  disabled: boolean;
  isSending: boolean;
  placeholder: string;
  sendLabel: string;
  sendingLabel: string;
  onTypingStart?: () => void;
  onTypingStop?: () => void;
  onSend: (body: string) => Promise<void>;
}) {
  const [value, setValue] = useState("");

  async function handleSubmit() {
    const normalized = value.trim();
    if (!normalized || disabled || isSending) {
      return;
    }
    await onSend(normalized);
    setValue("");
    onTypingStop?.();
  }

  return (
    <div className="rounded-xl border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <textarea
        value={value}
        disabled={disabled || isSending}
        onChange={(event) => {
          setValue(event.target.value);
          if (event.target.value.trim()) {
            onTypingStart?.();
          } else {
            onTypingStop?.();
          }
        }}
        placeholder={placeholder}
        className="min-h-24 w-full resize-none rounded-md border px-3 py-2 text-sm"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      />
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          disabled={disabled || isSending || !value.trim()}
          onClick={() => {
            void handleSubmit();
          }}
          className="inline-flex h-10 items-center rounded-md bg-blue-600 px-4 text-sm font-semibold text-white disabled:opacity-60"
        >
          {isSending ? sendingLabel : sendLabel}
        </button>
      </div>
    </div>
  );
}
