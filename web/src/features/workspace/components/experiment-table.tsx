'use client';

import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { Experiment } from '@/lib/domain';
import { formatDate, PageState, StatusBadge } from './shared';
import { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { parseLocale } from '@/i18n/config';

export function ExperimentTable({
  experiments,
  loading,
  error
}: {
  experiments: Experiment[];
  loading?: boolean;
  error?: string;
}) {
  const locale = parseLocale(useLocale());
  const t = useTranslations('Experiments');
  if (loading || error) return <PageState loading={loading} error={error} />;
  if (!experiments.length) return <PageState empty={t('noExperiments')} />;
  return (
    <Card>
      <CardContent className='overflow-x-auto p-0'>
        <table className='w-full text-sm'>
          <thead className='border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground'>
            <tr>
              <th className='px-4 py-3'>{t('tableExperiment')}</th>
              <th className='px-4 py-3'>{t('statusLabel')}</th>
              <th className='px-4 py-3'>{t('tableUpdated')}</th>
              <th className='px-4 py-3'>{t('lineage')}</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((experiment) => (
              <tr key={experiment.id} className='border-b last:border-0'>
                <td className='px-4 py-3'>
                  <Link
                    className='font-medium hover:underline'
                    href={`/dashboard/experiments/${experiment.id}`}
                  >
                    {experiment.title}
                  </Link>
                  <div className='text-xs text-muted-foreground'>{experiment.code}</div>
                </td>
                <td className='px-4 py-3'>
                  <StatusBadge status={experiment.status} />
                </td>
                <td className='whitespace-nowrap px-4 py-3 text-muted-foreground'>
                  {formatDate(experiment.updated_at, locale)}
                </td>
                <td className='px-4 py-3 text-xs text-muted-foreground'>
                  {experiment.parent_experiment_id ? t('cloned') : t('original')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

export function ExperimentList() {
  const [items, setItems] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    api
      .listExperiments()
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  return <ExperimentTable experiments={items} loading={loading} error={error} />;
}
