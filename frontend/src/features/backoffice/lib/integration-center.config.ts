import {
  Banknote,
  Box,
  CreditCard,
  Globe2,
  Languages,
  Mail,
  PackageCheck,
  ReceiptText,
  Send,
  SlidersHorizontal,
  Store,
  Truck,
  Wallet2,
  type LucideIcon,
} from "lucide-react";

import type { BackofficeCatalogCategory } from "@/features/backoffice/types/backoffice";
import type { IntegrationCenterToggleKey, IntegrationTranslatorProvider } from "@/features/backoffice/types/integration-center.types";

export type ToggleConfig = {
  key: IntegrationCenterToggleKey;
  labelKey: string;
  hintKey: string;
  icon: LucideIcon;
};

export type ToggleGroupConfig = {
  titleKey: string;
  icon: LucideIcon;
  items: ToggleConfig[];
};

export type TranslatorProviderConfig = {
  key: IntegrationTranslatorProvider;
  labelKey: string;
  hintKey: string;
  icon: LucideIcon;
};

export const GROUPS: ToggleGroupConfig[] = [
  {
    titleKey: "integrationCenter.groups.payments",
    icon: Wallet2,
    items: [
      { key: "payment.cash_on_delivery", labelKey: "integrationCenter.items.paymentCod.label", hintKey: "integrationCenter.items.paymentCod.hint", icon: Banknote },
      { key: "payment.monobank", labelKey: "integrationCenter.items.paymentMonobank.label", hintKey: "integrationCenter.items.paymentMonobank.hint", icon: CreditCard },
      { key: "payment.novapay", labelKey: "integrationCenter.items.paymentNovaPay.label", hintKey: "integrationCenter.items.paymentNovaPay.hint", icon: CreditCard },
      { key: "payment.liqpay", labelKey: "integrationCenter.items.paymentLiqPay.label", hintKey: "integrationCenter.items.paymentLiqPay.hint", icon: CreditCard },
    ],
  },
  {
    titleKey: "integrationCenter.groups.delivery",
    icon: Truck,
    items: [
      { key: "delivery.pickup", labelKey: "integrationCenter.items.deliveryPickup.label", hintKey: "integrationCenter.items.deliveryPickup.hint", icon: Store },
      { key: "delivery.nova_poshta", labelKey: "integrationCenter.items.deliveryNovaPoshta.label", hintKey: "integrationCenter.items.deliveryNovaPoshta.hint", icon: PackageCheck },
      { key: "delivery.courier", labelKey: "integrationCenter.items.deliveryCourier.label", hintKey: "integrationCenter.items.deliveryCourier.hint", icon: Truck },
    ],
  },
  {
    titleKey: "integrationCenter.groups.suppliers",
    icon: Truck,
    items: [
      { key: "supplier.utr", labelKey: "integrationCenter.items.supplierUtr.label", hintKey: "integrationCenter.items.supplierUtr.hint", icon: Box },
      { key: "supplier.gpl", labelKey: "integrationCenter.items.supplierGpl.label", hintKey: "integrationCenter.items.supplierGpl.hint", icon: Box },
    ],
  },
  {
    titleKey: "integrationCenter.groups.system",
    icon: SlidersHorizontal,
    items: [
      { key: "integration.vchasno_kasa", labelKey: "integrationCenter.items.integrationVchasno.label", hintKey: "integrationCenter.items.integrationVchasno.hint", icon: ReceiptText },
      { key: "integration.seo", labelKey: "integrationCenter.items.integrationSeo.label", hintKey: "integrationCenter.items.integrationSeo.hint", icon: Globe2 },
      { key: "integration.email", labelKey: "integrationCenter.items.integrationEmail.label", hintKey: "integrationCenter.items.integrationEmail.hint", icon: Mail },
    ],
  },
];

export const PAYMENTS_GROUP = GROUPS[0];
export const DELIVERY_GROUP = GROUPS[1];
export const SUPPLIERS_GROUP = GROUPS[2];
export const SYSTEM_GROUP = GROUPS[3];

export const TRANSLATOR_PROVIDERS: TranslatorProviderConfig[] = [
  {
    key: "google",
    labelKey: "integrationCenter.translator.providers.google.label",
    hintKey: "integrationCenter.translator.providers.google.hint",
    icon: Globe2,
  },
  {
    key: "libretranslate",
    labelKey: "integrationCenter.translator.providers.libretranslate.label",
    hintKey: "integrationCenter.translator.providers.libretranslate.hint",
    icon: Languages,
  },
];

export const TELEGRAM_GROUP: ToggleGroupConfig = {
  titleKey: "integrationCenter.groups.telegram",
  icon: Send,
  items: [
    { key: "integration.telegram", labelKey: "integrationCenter.items.integrationTelegram.label", hintKey: "integrationCenter.items.integrationTelegram.hint", icon: Send },
    { key: "integration.telegram_ops", labelKey: "integrationCenter.items.integrationTelegramOps.label", hintKey: "integrationCenter.items.integrationTelegramOps.hint", icon: Send },
    { key: "integration.telegram_support", labelKey: "integrationCenter.items.integrationTelegramSupport.label", hintKey: "integrationCenter.items.integrationTelegramSupport.hint", icon: Send },
    { key: "integration.telegram_system", labelKey: "integrationCenter.items.integrationTelegramSystem.label", hintKey: "integrationCenter.items.integrationTelegramSystem.hint", icon: Send },
  ],
};

export function getLocalizedCategoryName(category: BackofficeCatalogCategory, locale: string): string {
  if (locale === "ru") {
    return category.name_ru || category.name_uk || category.name;
  }
  if (locale === "en") {
    return category.name_en || category.name_uk || category.name;
  }
  return category.name_uk || category.name;
}

export function buildCategoryPath(
  category: BackofficeCatalogCategory,
  byId: Record<string, BackofficeCatalogCategory>,
  locale: string,
): string {
  const chain: string[] = [];
  const visited = new Set<string>();
  let current: BackofficeCatalogCategory | undefined = category;
  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    chain.unshift(getLocalizedCategoryName(current, locale));
    current = current.parent ? byId[current.parent] : undefined;
  }
  return chain.join(" > ");
}

export function buildCompactCategoryLabel(label: string): string {
  const raw = String(label || "").trim();
  if (!raw) {
    return "";
  }
  const parts = raw.split(">").map((part) => part.trim()).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : raw;
}

export function normalizeReturnsPhoneLocalDigits(value: string): string {
  const digitsOnly = String(value || "").replace(/\D/g, "");
  if (!digitsOnly) {
    return "";
  }
  if (digitsOnly === "3" || digitsOnly === "38" || digitsOnly === "380") {
    return "";
  }
  if (digitsOnly.startsWith("380")) {
    return `0${digitsOnly.slice(3)}`.slice(0, 10);
  }
  if (digitsOnly.startsWith("38")) {
    const tail = digitsOnly.slice(2);
    if (!tail) {
      return "";
    }
    return (tail.startsWith("0") ? tail : `0${tail}`).slice(0, 10);
  }
  if (digitsOnly.startsWith("0")) {
    return digitsOnly.slice(0, 10);
  }
  return `0${digitsOnly}`.slice(0, 10);
}

export function formatReturnsPhoneInput(value: string): string {
  const localDigits = normalizeReturnsPhoneLocalDigits(value);
  if (!localDigits) {
    return "";
  }
  let output = "+38 (";
  output += localDigits.slice(0, Math.min(3, localDigits.length));
  if (localDigits.length > 3) {
    output += ")";
  }
  if (localDigits.length > 3) {
    output += ` ${localDigits.slice(3, 6)}`;
  }
  if (localDigits.length > 6) {
    output += `-${localDigits.slice(6, 8)}`;
  }
  if (localDigits.length > 8) {
    output += `-${localDigits.slice(8, 10)}`;
  }
  return output;
}
