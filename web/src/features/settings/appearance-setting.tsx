'use client';

import { useTranslations } from 'next-intl';
import { useTheme } from 'next-themes';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { startThemeTransition } from '@/lib/theme-transition';

export function AppearanceSetting({ compact = false }: { compact?: boolean }) {
  const { theme, setTheme } = useTheme();
  const t = useTranslations('Settings');
  const options = [
    ['system', t('system')],
    ['light', t('light')],
    ['dark', t('dark')]
  ] as const;
  return (
    <div
      className={cn('flex flex-wrap gap-1.5', compact && 'grid grid-cols-3')}
      role='radiogroup'
      aria-label={t('appearance')}
    >
      {options.map(([value, label]) => (
        <Button
          key={value}
          type='button'
          size='xs'
          variant={theme === value ? 'secondary' : 'outline'}
          className={cn('text-xs', compact && 'w-full px-1')}
          aria-pressed={theme === value}
          onClick={() => startThemeTransition(() => setTheme(value))}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}
