'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Switch } from '@/components/ui/switch';
import { readDevtoolsPreference, writeDevtoolsPreference } from './preferences-storage';

export function DeveloperSetting() {
  const t = useTranslations('Settings');
  const [enabled, setEnabled] = useState(
    () =>
      process.env.NODE_ENV === 'development' &&
      typeof window !== 'undefined' &&
      readDevtoolsPreference()
  );
  if (process.env.NODE_ENV !== 'development') return null;
  function toggle(next: boolean) {
    setEnabled(next);
    writeDevtoolsPreference(next);
  }
  return (
    <div className='flex items-center justify-between gap-4 rounded-lg border px-3 py-3'>
      <div>
        <p className='text-sm font-medium'>{t('reactQueryDevtools')}</p>
        <p className='mt-1 text-xs text-muted-foreground'>{t('reactQueryDevtoolsHint')}</p>
      </div>
      <Switch checked={enabled} onCheckedChange={toggle} aria-label={t('reactQueryDevtools')} />
    </div>
  );
}
