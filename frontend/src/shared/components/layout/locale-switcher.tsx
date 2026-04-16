"use client";

import { Languages } from "lucide-react";
import { useLocale } from "next-intl";

import { usePathname, useRouter } from "@/i18n/navigation";
import type { AppLocale } from "@/i18n/routing";

const localeOptions: AppLocale[] = ["uk", "ru", "en"];

export function LocaleSwitcher() {
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const pathname = usePathname();

  return (
    <label className="inline-flex items-center gap-2 rounded-lg border px-3 py-2" style={{ borderColor: "var(--border)" }}>
      <Languages size={16} />
      <select
        value={locale}
        onChange={(event) => router.replace(pathname, { locale: event.target.value as AppLocale })}
        className="bg-transparent text-sm outline-none"
      >
        {localeOptions.map((item) => (
          <option key={item} value={item}>
            {item.toUpperCase()}
          </option>
        ))}
      </select>
    </label>
  );
}
