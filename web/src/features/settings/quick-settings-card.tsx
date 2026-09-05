'use client';

import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { Settings2 } from 'lucide-react';
import { AppearanceSetting } from './appearance-setting';
import { LocaleSetting } from './locale-setting';

export function QuickSettingsCard({
  onMouseEnter,
  onMouseLeave
}: {
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const t = useTranslations('Settings');
  return (
    <div
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className='w-72 space-y-4 rounded-xl border bg-popover p-4 text-popover-foreground shadow-xl ring-1 ring-foreground/10'
    >
      <div>
        <p className='text-sm font-semibold'>{t('quickTitle')}</p>
        <p className='mt-1 text-xs text-muted-foreground'>{t('quickHint')}</p>
      </div>
      <div className='space-y-2'>
        <p className='text-xs font-medium'>{t('language')}</p>
        <LocaleSetting compact />
      </div>
      <div className='space-y-2'>
        <p className='text-xs font-medium'>{t('appearance')}</p>
        <AppearanceSetting compact />
      </div>
      <Link
        href='/dashboard/settings'
        className='flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-xs font-medium hover:bg-muted'
        onClick={onMouseLeave}
      >
        <Settings2 className='size-3.5' />
        {t('openDetails')}
      </Link>
    </div>
  );
}
