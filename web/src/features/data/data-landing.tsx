'use client';

import { useEffect, useState } from 'react';
import { Database, Plus } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { api, ApiError } from '@/lib/api-client';
import { useProjectScope } from '@/features/workspace/project-scope/project-scope-context';

export function DataLanding() {
  const t = useTranslations('DataLanding');
  const common = useTranslations('Common');
  const {
    activeProject,
    projects,
    loading: projectsLoading,
    error: projectsError,
    openCreateProject
  } = useProjectScope();
  const [count, setCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeProject) {
      setCount(null);
      setError(null);
      return;
    }
    setLoading(true);
    api
      .getProjectContext(activeProject.id)
      .then((context) => {
        setCount(context.counts.data ?? 0);
        setError(null);
      })
      .catch((cause) =>
        setError(
          cause instanceof ApiError
            ? cause.message
            : cause instanceof Error
              ? cause.message
              : t('loadError')
        )
      )
      .finally(() => setLoading(false));
  }, [activeProject, t]);

  return (
    <main className='mx-auto w-full max-w-[1320px] px-4 py-7 md:px-8 md:py-10'>
      <div className='mb-8'>
        <p className='font-mono text-[10px] uppercase tracking-[0.2em] text-primary'>
          {t('eyebrow')}
        </p>
        <h1 className='mt-2 flex items-center gap-3 text-3xl font-semibold tracking-tight'>
          <Database className='size-7 text-primary' />
          {t('title')}
        </h1>
        <p className='mt-2 max-w-2xl text-sm text-muted-foreground'>{t('description')}</p>
      </div>
      {projectsLoading ? (
        <div className='rounded-2xl border bg-card/70 px-6 py-16 text-center text-sm text-muted-foreground'>
          {common('loading')}
        </div>
      ) : projectsError ? (
        <div
          className='rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-5 text-sm text-destructive'
          role='alert'
        >
          {projectsError}
        </div>
      ) : !activeProject ? (
        <div className='rounded-2xl border border-dashed bg-card/70 px-6 py-16 text-center'>
          <p className='text-sm text-muted-foreground'>{t('noProject')}</p>
          {projects.length === 0 && (
            <Button className='mt-4' onClick={openCreateProject}>
              <Plus /> {t('createProject')}
            </Button>
          )}
        </div>
      ) : (
        <div className='grid gap-4 sm:grid-cols-[minmax(0,1fr)_14rem]'>
          <section className='rounded-2xl border bg-card/80 p-6'>
            <p className='text-xs text-muted-foreground'>{t('currentProject')}</p>
            <h2 className='mt-2 text-xl font-semibold'>{activeProject.title}</h2>
            <p className='mt-1 font-mono text-xs text-muted-foreground'>{activeProject.code}</p>
            <p className='mt-8 text-sm text-muted-foreground'>{t('deferred')}</p>
          </section>
          <section className='rounded-2xl border bg-card/80 p-6'>
            <p className='text-xs text-muted-foreground'>{t('recordCount')}</p>
            <p className='mt-2 text-4xl font-semibold tracking-tight'>
              {loading ? '…' : error ? '—' : (count ?? 0)}
            </p>
            {error && <p className='mt-2 text-xs text-destructive'>{error}</p>}
          </section>
        </div>
      )}
    </main>
  );
}
