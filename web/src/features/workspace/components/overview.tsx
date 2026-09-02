'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api-client';
import type { Experiment, Project } from '@/lib/domain';
import { ExperimentTable } from './experiment-table';
import { ButtonLink, PageHeader, PageState } from './shared';
import { useTranslations } from 'next-intl';

export function Overview() {
  const t = useTranslations('Overview');
  const [projects, setProjects] = useState<Project[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    Promise.all([api.listProjects(), api.listExperiments()])
      .then(([p, e]) => {
        setProjects(p);
        setExperiments(e);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);
  const active = useMemo(() => projects.filter((p) => p.status === 'active').length, [projects]);
  return (
    <div className='flex flex-1 flex-col px-4 pt-4 pb-8 md:px-6'>
      <PageHeader
        title={t('title')}
        description={t('description')}
        action={<ButtonLink href='/dashboard/projects'>{t('newProject')}</ButtonLink>}
      />
      {loading || error ? (
        <PageState loading={loading} error={error} />
      ) : (
        <>
          <div className='mb-8 grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-3'>
            {[
              [t('activeProjects'), active],
              [t('experiments'), experiments.length],
              [t('completed'), experiments.filter((e) => e.status === 'completed').length]
            ].map(([label, value]) => (
              <div key={label} className='bg-card px-4 py-3'>
                <p className='text-xs font-medium tracking-wide text-muted-foreground uppercase'>
                  {label}
                </p>
                <p className='mt-1 text-2xl font-semibold tabular-nums'>{value}</p>
              </div>
            ))}
          </div>
          <div className='mb-8 flex items-start gap-3 rounded-lg border border-dashed border-primary/40 bg-primary/5 px-4 py-3 text-sm text-muted-foreground'>
            <span className='mt-1 size-2 shrink-0 rounded-full bg-primary' aria-hidden='true' />
            <p>
              <span className='font-medium text-foreground'>{t('syntheticDemo')}</span> ·{' '}
              {t('demoDescription')}
            </p>
          </div>
          <div className='mb-3 flex items-center justify-between border-b pb-3'>
            <div>
              <p className='text-xs font-medium tracking-wide text-muted-foreground uppercase'>
                {t('researchActivity')}
              </p>
              <h2 className='mt-1 text-lg font-semibold'>{t('recentExperiments')}</h2>
            </div>
            <ButtonLink href='/dashboard/experiments' variant='ghost' size='sm'>
              {t('viewAll')} →
            </ButtonLink>
          </div>
          <ExperimentTable
            experiments={experiments
              .toSorted((a, b) => b.updated_at.localeCompare(a.updated_at))
              .slice(0, 8)}
          />
        </>
      )}
    </div>
  );
}
