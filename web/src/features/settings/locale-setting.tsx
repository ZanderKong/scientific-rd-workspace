'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useTransition } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  LOCALE_COOKIE_MAX_AGE,
  LOCALE_COOKIE_NAME,
  parseLocale,
  type AppLocale
} from '@/i18n/config';

export function setLocalePreference(nextLocale: AppLocale) {
  document.cookie = `${LOCALE_COOKIE_NAME}=${nextLocale}; Path=/; Max-Age=${LOCALE_COOKIE_MAX_AGE}; SameSite=Lax`;
}

export function LocaleSetting({ compact = false }: { compact?: boolean }) {
  const locale = parseLocale(useLocale());
  const t = useTranslations('Locale');
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function selectLocale(nextLocale: AppLocale) {
    if (nextLocale === locale || isPending) return;
    setLocalePreference(nextLocale);
    startTransition(() => router.refresh());
  }

  return (
    <div
      className={cn(
        'inline-flex items-center gap-0.5 rounded-md bg-muted/60 p-0.5',
        compact && 'w-full'
      )}
      role='group'
      aria-label={t('label')}
    >
      {(
        [
          ['zh-CN', t('chinese')],
          ['en', t('english')]
        ] as const
      ).map(([value, label]) => (
        <Button
          key={value}
          type='button'
          variant={locale === value ? 'secondary' : 'ghost'}
          size='xs'
          className={cn('h-7 px-2 text-xs', compact && 'flex-1')}
          disabled={isPending}
          aria-pressed={locale === value}
          onClick={() => selectLocale(value)}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}
