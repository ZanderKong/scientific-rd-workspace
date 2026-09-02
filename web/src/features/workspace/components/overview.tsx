'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api-client';
import type { Experiment, Project } from '@/lib/domain';
import { ExperimentTable } from './experiment-table';
import { ButtonLink, PageHeader, PageState } from './shared';
import { useTranslations } from 'next-intl';
import { MetricStrip, SectionHeader } from './scientific-ui';

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
          <MetricStrip
            className='mb-8 sm:grid-cols-3'
            items={[
              { label: t('activeProjects'), value: active, tone: 'primary' },
              { label: t('experiments'), value: experiments.length },
              {
                label: t('completed'),
                value: experiments.filter((e) => e.status === 'completed').length
              }
            ]}
          />
          <div className='mb-8 flex items-start gap-3 rounded-lg border border-dashed border-primary/40 bg-primary/5 px-4 py-3 text-sm text-muted-foreground'>
            <span className='mt-1 size-2 shrink-0 rounded-full bg-primary' aria-hidden='true' />
            <p>
              <span className='font-medium text-foreground'>{t('syntheticDemo')}</span> ·{' '}
              {t('demoDescription')}
            </p>
          </div>
          <SectionHeader
            eyebrow={t('researchActivity')}
            title={t('recentExperiments')}
            action={
              <ButtonLink href='/dashboard/experiments' variant='ghost' size='sm'>
                {t('viewAll')} →
              </ButtonLink>
            }
          />
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
