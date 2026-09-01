'use client';

import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { Experiment } from '@/lib/domain';
import { formatDate, PageState, StatusBadge } from './shared';
import { useEffect, useState } from 'react';

export function ExperimentTable({
  experiments,
  loading,
  error
}: {
  experiments: Experiment[];
  loading?: boolean;
  error?: string;
}) {
  if (loading || error) return <PageState loading={loading} error={error} />;
  if (!experiments.length) return <PageState empty='No experiments yet.' />;
  return (
    <Card>
      <CardContent className='overflow-x-auto p-0'>
        <table className='w-full text-sm'>
          <thead className='border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground'>
            <tr>
              <th className='px-4 py-3'>Experiment</th>
              <th className='px-4 py-3'>Status</th>
              <th className='px-4 py-3'>Updated</th>
              <th className='px-4 py-3'>Lineage</th>
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
                  {formatDate(experiment.updated_at)}
                </td>
                <td className='px-4 py-3 text-xs text-muted-foreground'>
                  {experiment.parent_experiment_id ? 'Cloned experiment' : 'Original record'}
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
