'use client';

import { useTranslations } from 'next-intl';
import { AppearanceSetting } from './appearance-setting';
import { AboutSetting } from './about-setting';
import { DeveloperSetting } from './developer-setting';
import { LocaleSetting } from './locale-setting';

export function SettingsPage() {
  const t = useTranslations('Settings');
  return (
    <main className='mx-auto w-full max-w-4xl px-4 py-7 md:px-8 md:py-10'>
      <div className='mb-8'>
        <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
          {t('eyebrow')}
        </p>
        <h1 className='mt-2 text-3xl font-semibold tracking-tight'>{t('title')}</h1>
        <p className='mt-2 text-sm text-muted-foreground'>{t('description')}</p>
      </div>
      <div className='grid gap-5'>
        <section className='rounded-2xl border bg-card/80 p-5'>
          <h2 className='text-base font-semibold'>{t('language')}</h2>
          <p className='mt-1 mb-4 text-xs text-muted-foreground'>{t('languageHint')}</p>
          <LocaleSetting />
        </section>
        <section className='rounded-2xl border bg-card/80 p-5'>
          <h2 className='text-base font-semibold'>{t('appearance')}</h2>
          <p className='mt-1 mb-4 text-xs text-muted-foreground'>{t('appearanceHint')}</p>
          <AppearanceSetting />
        </section>
        <section className='rounded-2xl border bg-card/80 p-5'>
          <h2 className='text-base font-semibold'>{t('developer')}</h2>
          <p className='mt-1 mb-4 text-xs text-muted-foreground'>{t('developerHint')}</p>
          <DeveloperSetting />
        </section>
        <section className='rounded-2xl border bg-card/80 p-5'>
          <h2 className='text-base font-semibold'>{t('about')}</h2>
          <p className='mt-1 mb-4 text-xs text-muted-foreground'>{t('aboutHint')}</p>
          <AboutSetting />
        </section>
      </div>
    </main>
  );
}
