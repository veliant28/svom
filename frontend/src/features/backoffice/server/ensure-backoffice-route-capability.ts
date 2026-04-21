import type { BackofficeCapabilityCode } from "@/features/backoffice/lib/capabilities";
import { requireBackofficeAccess } from "@/features/backoffice/server/require-backoffice-access";

export async function ensureBackofficeRouteCapability(
  localeOrParams: string | Promise<{ locale: string }>,
  capability: BackofficeCapabilityCode | BackofficeCapabilityCode[],
): Promise<void> {
  const locale = typeof localeOrParams === "string" ? localeOrParams : (await localeOrParams).locale;
  await requireBackofficeAccess(locale, capability);
}
