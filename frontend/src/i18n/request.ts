import { hasLocale } from "next-intl";
import { getRequestConfig } from "next-intl/server";

import { routing } from "./routing";

type Messages = Record<string, unknown>;
type AppLocale = (typeof routing.locales)[number];
type MessagesLoader = () => Promise<Messages>;

type LocaleModuleLoaders = {
  common: MessagesLoader;
  auth: MessagesLoader;
  catalog: MessagesLoader;
  garage: MessagesLoader;
  search: MessagesLoader;
  product: MessagesLoader;
  commerce: MessagesLoader;
  backofficeCommon: MessagesLoader;
  backofficeNavigation: MessagesLoader;
  backofficeDashboard: MessagesLoader;
  backofficeImportRuns: MessagesLoader;
  backofficeImportErrors: MessagesLoader;
  backofficeImportQuality: MessagesLoader;
  backofficeAutocatalog: MessagesLoader;
  backofficeSuppliers: MessagesLoader;
  backofficeUtr: MessagesLoader;
  backofficeGpl: MessagesLoader;
  backofficeImports: MessagesLoader;
  backofficeAuth: MessagesLoader;
  backofficeErrors: MessagesLoader;
};

const messagesCache = new Map<AppLocale, Messages>();
const messagesInflight = new Map<AppLocale, Promise<Messages>>();
const shouldCacheMessages = process.env.NODE_ENV === "production";

const localeModuleLoaders: Record<AppLocale, LocaleModuleLoaders> = {
  en: {
    common: () => import("../messages/en/common.json").then((module) => module.default as Messages),
    auth: () => import("../messages/en/auth.json").then((module) => module.default as Messages),
    catalog: () => import("../messages/en/catalog.json").then((module) => module.default as Messages),
    garage: () => import("../messages/en/garage.json").then((module) => module.default as Messages),
    search: () => import("../messages/en/search.json").then((module) => module.default as Messages),
    product: () => import("../messages/en/product.json").then((module) => module.default as Messages),
    commerce: () => import("../messages/en/commerce.json").then((module) => module.default as Messages),
    backofficeCommon: () =>
      import("../messages/en/backoffice/common.json").then((module) => module.default as Messages),
    backofficeNavigation: () =>
      import("../messages/en/backoffice/navigation.json").then((module) => module.default as Messages),
    backofficeDashboard: () =>
      import("../messages/en/backoffice/dashboard.json").then((module) => module.default as Messages),
    backofficeImportRuns: () =>
      import("../messages/en/backoffice/import-runs.json").then((module) => module.default as Messages),
    backofficeImportErrors: () =>
      import("../messages/en/backoffice/import-errors.json").then((module) => module.default as Messages),
    backofficeImportQuality: () =>
      import("../messages/en/backoffice/import-quality.json").then((module) => module.default as Messages),
    backofficeAutocatalog: () =>
      import("../messages/en/backoffice/autocatalog.json").then((module) => module.default as Messages),
    backofficeSuppliers: () =>
      import("../messages/en/backoffice/suppliers.json").then((module) => module.default as Messages),
    backofficeUtr: () => import("../messages/en/backoffice/utr.json").then((module) => module.default as Messages),
    backofficeGpl: () => import("../messages/en/backoffice/gpl.json").then((module) => module.default as Messages),
    backofficeImports: () =>
      import("../messages/en/backoffice/imports.json").then((module) => module.default as Messages),
    backofficeAuth: () =>
      import("../messages/en/backoffice/auth.json").then((module) => module.default as Messages),
    backofficeErrors: () =>
      import("../messages/en/backoffice/errors.json").then((module) => module.default as Messages),
  },
  ru: {
    common: () => import("../messages/ru/common.json").then((module) => module.default as Messages),
    auth: () => import("../messages/ru/auth.json").then((module) => module.default as Messages),
    catalog: () => import("../messages/ru/catalog.json").then((module) => module.default as Messages),
    garage: () => import("../messages/ru/garage.json").then((module) => module.default as Messages),
    search: () => import("../messages/ru/search.json").then((module) => module.default as Messages),
    product: () => import("../messages/ru/product.json").then((module) => module.default as Messages),
    commerce: () => import("../messages/ru/commerce.json").then((module) => module.default as Messages),
    backofficeCommon: () =>
      import("../messages/ru/backoffice/common.json").then((module) => module.default as Messages),
    backofficeNavigation: () =>
      import("../messages/ru/backoffice/navigation.json").then((module) => module.default as Messages),
    backofficeDashboard: () =>
      import("../messages/ru/backoffice/dashboard.json").then((module) => module.default as Messages),
    backofficeImportRuns: () =>
      import("../messages/ru/backoffice/import-runs.json").then((module) => module.default as Messages),
    backofficeImportErrors: () =>
      import("../messages/ru/backoffice/import-errors.json").then((module) => module.default as Messages),
    backofficeImportQuality: () =>
      import("../messages/ru/backoffice/import-quality.json").then((module) => module.default as Messages),
    backofficeAutocatalog: () =>
      import("../messages/ru/backoffice/autocatalog.json").then((module) => module.default as Messages),
    backofficeSuppliers: () =>
      import("../messages/ru/backoffice/suppliers.json").then((module) => module.default as Messages),
    backofficeUtr: () => import("../messages/ru/backoffice/utr.json").then((module) => module.default as Messages),
    backofficeGpl: () => import("../messages/ru/backoffice/gpl.json").then((module) => module.default as Messages),
    backofficeImports: () =>
      import("../messages/ru/backoffice/imports.json").then((module) => module.default as Messages),
    backofficeAuth: () =>
      import("../messages/ru/backoffice/auth.json").then((module) => module.default as Messages),
    backofficeErrors: () =>
      import("../messages/ru/backoffice/errors.json").then((module) => module.default as Messages),
  },
  uk: {
    common: () => import("../messages/uk/common.json").then((module) => module.default as Messages),
    auth: () => import("../messages/uk/auth.json").then((module) => module.default as Messages),
    catalog: () => import("../messages/uk/catalog.json").then((module) => module.default as Messages),
    garage: () => import("../messages/uk/garage.json").then((module) => module.default as Messages),
    search: () => import("../messages/uk/search.json").then((module) => module.default as Messages),
    product: () => import("../messages/uk/product.json").then((module) => module.default as Messages),
    commerce: () => import("../messages/uk/commerce.json").then((module) => module.default as Messages),
    backofficeCommon: () =>
      import("../messages/uk/backoffice/common.json").then((module) => module.default as Messages),
    backofficeNavigation: () =>
      import("../messages/uk/backoffice/navigation.json").then((module) => module.default as Messages),
    backofficeDashboard: () =>
      import("../messages/uk/backoffice/dashboard.json").then((module) => module.default as Messages),
    backofficeImportRuns: () =>
      import("../messages/uk/backoffice/import-runs.json").then((module) => module.default as Messages),
    backofficeImportErrors: () =>
      import("../messages/uk/backoffice/import-errors.json").then((module) => module.default as Messages),
    backofficeImportQuality: () =>
      import("../messages/uk/backoffice/import-quality.json").then((module) => module.default as Messages),
    backofficeAutocatalog: () =>
      import("../messages/uk/backoffice/autocatalog.json").then((module) => module.default as Messages),
    backofficeSuppliers: () =>
      import("../messages/uk/backoffice/suppliers.json").then((module) => module.default as Messages),
    backofficeUtr: () => import("../messages/uk/backoffice/utr.json").then((module) => module.default as Messages),
    backofficeGpl: () => import("../messages/uk/backoffice/gpl.json").then((module) => module.default as Messages),
    backofficeImports: () =>
      import("../messages/uk/backoffice/imports.json").then((module) => module.default as Messages),
    backofficeAuth: () =>
      import("../messages/uk/backoffice/auth.json").then((module) => module.default as Messages),
    backofficeErrors: () =>
      import("../messages/uk/backoffice/errors.json").then((module) => module.default as Messages),
  },
};

function getBackofficeBlock(messages: Messages): Messages {
  const backoffice = messages.backoffice;
  if (typeof backoffice === "object" && backoffice !== null && !Array.isArray(backoffice)) {
    return backoffice as Messages;
  }
  return {};
}

async function loadModule(locale: AppLocale, name: string, loader: MessagesLoader): Promise<Messages> {
  try {
    return await loader();
  } catch (error) {
    console.error(`[i18n] Failed to load messages module: ${locale}/${name}.json`, error);
    return {};
  }
}

async function loadMessages(locale: AppLocale): Promise<Messages> {
  if (shouldCacheMessages) {
    const cached = messagesCache.get(locale);
    if (cached) {
      return cached;
    }

    const inflight = messagesInflight.get(locale);
    if (inflight) {
      return inflight;
    }
  }

  const loadPromise = (async () => {
    const loaders = localeModuleLoaders[locale];
    const [
      common,
      auth,
      catalog,
      garage,
      search,
      product,
      commerce,
      backofficeCommon,
      backofficeNavigation,
      backofficeDashboard,
      backofficeImportRuns,
      backofficeImportErrors,
      backofficeImportQuality,
      backofficeAutocatalog,
      backofficeSuppliers,
      backofficeUtr,
      backofficeGpl,
      backofficeImports,
      backofficeAuth,
      backofficeErrors,
    ] = await Promise.all([
      loadModule(locale, "common", loaders.common),
      loadModule(locale, "auth", loaders.auth),
      loadModule(locale, "catalog", loaders.catalog),
      loadModule(locale, "garage", loaders.garage),
      loadModule(locale, "search", loaders.search),
      loadModule(locale, "product", loaders.product),
      loadModule(locale, "commerce", loaders.commerce),
      loadModule(locale, "backoffice/common", loaders.backofficeCommon),
      loadModule(locale, "backoffice/navigation", loaders.backofficeNavigation),
      loadModule(locale, "backoffice/dashboard", loaders.backofficeDashboard),
      loadModule(locale, "backoffice/import-runs", loaders.backofficeImportRuns),
      loadModule(locale, "backoffice/import-errors", loaders.backofficeImportErrors),
      loadModule(locale, "backoffice/import-quality", loaders.backofficeImportQuality),
      loadModule(locale, "backoffice/autocatalog", loaders.backofficeAutocatalog),
      loadModule(locale, "backoffice/suppliers", loaders.backofficeSuppliers),
      loadModule(locale, "backoffice/utr", loaders.backofficeUtr),
      loadModule(locale, "backoffice/gpl", loaders.backofficeGpl),
      loadModule(locale, "backoffice/imports", loaders.backofficeImports),
      loadModule(locale, "backoffice/auth", loaders.backofficeAuth),
      loadModule(locale, "backoffice/errors", loaders.backofficeErrors),
    ]);

    const merged = {
      ...common,
      ...auth,
      ...catalog,
      ...garage,
      ...search,
      ...product,
      ...commerce,
      backoffice: {
        ...getBackofficeBlock(backofficeCommon),
        ...getBackofficeBlock(backofficeNavigation),
        ...getBackofficeBlock(backofficeDashboard),
        ...getBackofficeBlock(backofficeImportRuns),
        ...getBackofficeBlock(backofficeImportErrors),
        ...getBackofficeBlock(backofficeImportQuality),
        ...getBackofficeBlock(backofficeAutocatalog),
        ...getBackofficeBlock(backofficeSuppliers),
        ...getBackofficeBlock(backofficeUtr),
        ...getBackofficeBlock(backofficeGpl),
        ...getBackofficeBlock(backofficeImports),
        ...getBackofficeBlock(backofficeAuth),
        ...getBackofficeBlock(backofficeErrors),
      },
    };
    if (shouldCacheMessages) {
      messagesCache.set(locale, merged);
    }
    return merged;
  })();

  if (shouldCacheMessages) {
    messagesInflight.set(locale, loadPromise);
  }
  try {
    return await loadPromise;
  } finally {
    if (shouldCacheMessages) {
      messagesInflight.delete(locale);
    }
  }
}

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;
  const messages = await loadMessages(locale);

  return {
    locale,
    messages,
  };
});
