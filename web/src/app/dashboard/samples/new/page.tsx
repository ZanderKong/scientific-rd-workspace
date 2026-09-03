'use client';

import { useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useLocale } from 'next-intl';
import { api } from '@/lib/api-client';
import type { SampleRecord } from '@/lib/domain';
import { SampleComposer } from '@/features/workspace/sample-record/sample-composer';

export default function NewSamplePage() {
  const locale = useLocale();
  const params = useSearchParams();
  const projectId = params.get('project');
  const fromId = params.get('from');
  const [source, setSource] = useState<SampleRecord | null>(null);
  const [loading, setLoading] = useState(Boolean(fromId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!fromId) {
      setLoading(false);
      return;
    }
    api
      .getSampleRecord(fromId)
      .then(setSource)
      .catch((cause) =>
        setError(cause instanceof Error ? cause.message : 'Unable to load source Sample')
      )
      .finally(() => setLoading(false));
  }, [fromId]);

  if (loading)
    return (
      <div className='px-8 py-16 text-center text-sm text-muted-foreground'>
        {locale === 'zh-CN' ? '正在载入样品草稿…' : 'Loading Sample draft…'}
      </div>
    );
  if (error)
    return (
      <div
        role='alert'
        className='m-8 rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-5 text-sm text-destructive'
      >
        {error}
      </div>
    );
  return (
    <SampleComposer
      projectId={projectId}
      initialRecord={source}
      mode='create'
      zh={locale === 'zh-CN'}
    />
  );
}
