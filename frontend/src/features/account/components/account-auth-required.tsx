"use client";

import { Link } from "@/i18n/navigation";

type AccountAuthRequiredProps = {
  title: string;
  message: string;
  loginLabel: string;
};

export function AccountAuthRequired({ title, message, loginLabel }: AccountAuthRequiredProps) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">{title}</h1>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {message}
      </p>
      <Link
        href="/login"
        className="mt-4 inline-flex h-10 items-center rounded-lg border px-3 text-sm font-medium"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
      >
        {loginLabel}
      </Link>
    </section>
  );
}
