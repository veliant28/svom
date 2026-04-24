import type { Metadata } from "next";

import type {
  SeoEntityType,
  SeoLocale,
  SeoPublicConfig,
  SeoPublicMetaOverride,
  SeoPublicMetaTemplate,
  SeoPublicSiteSettings,
} from "@/features/seo/types";

type ResolveSeoMetadataParams = {
  config: SeoPublicConfig | null;
  path: string;
  locale: string;
  entityType: SeoEntityType;
  context?: Partial<Record<"name" | "brand" | "category" | "article" | "price" | "site_name", string>>;
  fallbackTitle?: string;
  fallbackDescription?: string;
};

function normalizeLocale(locale: string): SeoLocale {
  const value = String(locale || "").toLowerCase();
  if (value.startsWith("ru")) {
    return "ru";
  }
  if (value.startsWith("en")) {
    return "en";
  }
  return "uk";
}

function normalizePath(path: string): string {
  const value = String(path || "").trim();
  if (!value) {
    return "/";
  }
  return value.startsWith("/") ? value : `/${value}`;
}

function localized(settings: SeoPublicSiteSettings, key: "default_meta_title" | "default_meta_description" | "default_og_title" | "default_og_description", locale: SeoLocale): string {
  const localizedValue = settings[`${key}_${locale}`];
  if (localizedValue) {
    return localizedValue;
  }
  return settings[`${key}_uk`] || "";
}

function renderTemplate(value: string, context: Record<string, string>): string {
  let output = value || "";
  if (!output) {
    return "";
  }
  Object.entries(context).forEach(([key, data]) => {
    output = output.replaceAll(`{${key}}`, data);
  });
  return output.replace(/\s+/g, " ").trim();
}

function findOverride(overrides: SeoPublicMetaOverride[], path: string, locale: SeoLocale): SeoPublicMetaOverride | null {
  return overrides.find((item) => item.is_active && item.path === path && item.locale === locale) ?? null;
}

function findTemplate(templates: SeoPublicMetaTemplate[], entityType: SeoEntityType, locale: SeoLocale): SeoPublicMetaTemplate | null {
  return templates.find((item) => item.is_active && item.entity_type === entityType && item.locale === locale) ?? null;
}

function buildCanonical(baseUrl: string, path: string): string | undefined {
  const base = (baseUrl || "").trim().replace(/\/+$/, "");
  if (!base) {
    return undefined;
  }
  return `${base}${normalizePath(path)}`;
}

function resolveRobots(value: string): Metadata["robots"] {
  const normalized = String(value || "").toLowerCase();
  if (!normalized) {
    return undefined;
  }
  return {
    index: normalized.includes("index") && !normalized.includes("noindex"),
    follow: normalized.includes("follow") && !normalized.includes("nofollow"),
  };
}

export function resolveSeoMetadata(params: ResolveSeoMetadataParams): Metadata {
  const locale = normalizeLocale(params.locale);
  const path = normalizePath(params.path);
  const settings = params.config?.settings;
  const context = {
    name: params.context?.name || "",
    brand: params.context?.brand || "",
    category: params.context?.category || "",
    article: params.context?.article || "",
    price: params.context?.price || "",
    site_name: params.context?.site_name || "SVOM",
  };

  if (!settings || !settings.is_enabled) {
    return {
      title: params.fallbackTitle || context.name || "SVOM",
      description: params.fallbackDescription || "",
    };
  }

  const overrides = params.config?.overrides || [];
  const templates = params.config?.templates || [];
  const override = findOverride(overrides, path, locale);
  const template = override ? null : findTemplate(templates, params.entityType, locale);
  const defaultTitle = localized(settings, "default_meta_title", locale);
  const defaultDescription = localized(settings, "default_meta_description", locale);
  const defaultOgTitle = localized(settings, "default_og_title", locale);
  const defaultOgDescription = localized(settings, "default_og_description", locale);

  const title = override?.meta_title
    || (template ? renderTemplate(template.title_template, context) : "")
    || defaultTitle
    || params.fallbackTitle
    || context.name
    || "SVOM";
  const description = override?.meta_description
    || (template ? renderTemplate(template.description_template, context) : "")
    || defaultDescription
    || params.fallbackDescription
    || "";
  const ogTitle = override?.og_title
    || (template ? renderTemplate(template.og_title_template, context) : "")
    || defaultOgTitle
    || title;
  const ogDescription = override?.og_description
    || (template ? renderTemplate(template.og_description_template, context) : "")
    || defaultOgDescription
    || description;
  const canonical = override?.canonical_url || buildCanonical(settings.canonical_base_url, path);
  const robotsDirective = override?.robots_directive || settings.default_robots_directive;

  return {
    title,
    description,
    alternates: canonical ? { canonical } : undefined,
    robots: resolveRobots(robotsDirective),
    openGraph: {
      title: ogTitle,
      description: ogDescription,
      url: canonical,
      images: override?.og_image_url ? [{ url: override.og_image_url }] : undefined,
    },
  };
}
