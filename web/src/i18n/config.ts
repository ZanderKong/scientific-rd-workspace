export const LOCALES = ['zh-CN', 'en'] as const;

export type AppLocale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: AppLocale = 'zh-CN';
export const FALLBACK_LOCALE: AppLocale = 'en';
export const LOCALE_COOKIE_NAME = 'scientific_workspace_locale';
export const LOCALE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

export function isAppLocale(value: string | undefined | null): value is AppLocale {
  return value === 'zh-CN' || value === 'en';
}

export function parseLocale(value: string | undefined | null): AppLocale {
  return isAppLocale(value) ? value : DEFAULT_LOCALE;
}

export const BLOCKNOTE_LOCALE: Record<AppLocale, 'zh' | 'en'> = {
  'zh-CN': 'zh',
  en: 'en'
};
