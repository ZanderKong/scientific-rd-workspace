'use client';

import { useTranslations } from 'next-intl';

export function AboutSetting() {
  const t = useTranslations('Settings');
  const version = process.env.NEXT_PUBLIC_APP_VERSION || '0.3.0';
  const sha = process.env.NEXT_PUBLIC_GIT_SHA || t('unknown');
  return (
    <div className='grid gap-2 rounded-lg border px-3 py-3 text-sm'>
      <p className='font-medium'>{t('productName')}</p>
      <p className='text-xs text-muted-foreground'>{t('productDescription')}</p>
      <dl className='mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-[8rem_1fr]'>
        <dt>{t('appVersion')}</dt>
        <dd>{version}</dd>
        <dt>{t('buildCommit')}</dt>
        <dd className='font-mono'>{sha}</dd>
        <dt>{t('repository')}</dt>
        <dd>scientific-rd-workspace</dd>
      </dl>
    </div>
  );
}
