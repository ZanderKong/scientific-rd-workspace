'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useTransition } from 'react';
import { buttonVariants } from '@/components/ui/button';
import {
  LOCALE_COOKIE_MAX_AGE,
  LOCALE_COOKIE_NAME,
  type AppLocale,
  parseLocale
} from '@/i18n/config';
import { cn } from '@/lib/utils';

export function LocaleSwitcher() {
  const locale = parseLocale(useLocale());
  const t = useTranslations('Locale');
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function selectLocale(nextLocale: AppLocale) {
    if (nextLocale === locale || isPending) return;
    // The locale cookie is intentionally first-party and client-written so the
    // current route can be refreshed without introducing a URL prefix.
    // oxlint-disable-next-line react/immutability
    document.cookie = `${LOCALE_COOKIE_NAME}=${nextLocale}; Path=/; Max-Age=${LOCALE_COOKIE_MAX_AGE}; SameSite=Lax`;
    startTransition(() => router.refresh());
  }

  return (
    <div
      className='bg-muted/60 inline-flex items-center gap-0.5 rounded-md p-0.5'
      role='group'
      aria-label={t('label')}
    >
      {(
        [
          ['zh-CN', t('chinese')],
          ['en', t('english')]
        ] as const
      ).map(([value, label]) => (
        <button
          key={value}
          type='button'
          disabled={isPending}
          aria-pressed={locale === value}
          className={cn(
            buttonVariants({ variant: locale === value ? 'secondary' : 'ghost', size: 'xs' }),
            'h-7 px-2 text-xs'
          )}
          onClick={() => selectLocale(value)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
