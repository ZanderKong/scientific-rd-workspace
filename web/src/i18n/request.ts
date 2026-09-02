import { cookies } from 'next/headers';
import { getRequestConfig } from 'next-intl/server';
import { DEFAULT_LOCALE, LOCALE_COOKIE_NAME, parseLocale } from './config';

export default getRequestConfig(async () => {
  const locale = parseLocale((await cookies()).get(LOCALE_COOKIE_NAME)?.value ?? DEFAULT_LOCALE);
  const messages = (await import(`../../messages/${locale}.json`)).default;

  return { locale, messages };
});
