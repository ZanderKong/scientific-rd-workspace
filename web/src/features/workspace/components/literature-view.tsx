'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api-client';
import type { Evidence, Literature, Project } from '@/lib/domain';
import { PageHeader, PageState, StatusBadge } from './shared';
import { useTranslations } from 'next-intl';

export function LiteratureView() {
  const t = useTranslations('Literature');
  const common = useTranslations('Common');
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [items, setItems] = useState<Literature[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [title, setTitle] = useState('');
  const [authors, setAuthors] = useState('');
  const [doi, setDoi] = useState('');
  const [claim, setClaim] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    void api
      .listProjects()
      .then((rows) => {
        setProjects(rows);
        if (rows[0]) setProjectId(rows[0].id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : t('noLiterature')));
  }, [t]);
  const refresh = useCallback(async () => {
    if (!projectId) return;
    const [literature, records] = await Promise.all([
      api.listLiterature(projectId),
      api.listEvidence(projectId)
    ]);
    setItems(literature);
    setEvidence(records);
  }, [projectId]);
  useEffect(() => {
    void refresh().catch((e) => setError(e instanceof Error ? e.message : t('errorLoad')));
  }, [refresh, t]);
  async function create() {
    if (!projectId || !title.trim()) return;
    setError('');
    try {
      await api.createLiterature(projectId, {
        title,
        authors: authors ? [{ literal: authors }] : [],
        doi: doi || null
      });
      setTitle('');
      setAuthors('');
      setDoi('');
      setMessage(t('created'));
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('noLiterature'));
    }
  }
  async function createEvidence(literatureId: string) {
    if (!projectId || !claim.trim()) return;
    try {
      await api.createEvidence(projectId, {
        claim_text: claim,
        stance: 'supports',
        source: { type: 'literature', literature_id: literatureId }
      });
      setClaim('');
      setMessage(t('evidenceCreated'));
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('noEvidence'));
    }
  }
  if (error && !projects.length) return <PageState error={error} />;
  return (
    <div className='flex flex-1 flex-col gap-6 px-4 pt-4 pb-8 md:px-6'>
      <PageHeader title={t('title')} description={t('description')} />
      <select
        className='h-8 max-w-md rounded-lg border bg-background px-2 text-sm'
        value={projectId}
        onChange={(e) => setProjectId(e.target.value)}
      >
        <option value=''>{common('chooseProject')}</option>
        {projects.map((item) => (
          <option key={item.id} value={item.id}>
            {item.code} · {item.title}
          </option>
        ))}
      </select>
      {message ? (
        <p className='rounded-md bg-primary/10 px-3 py-2 text-sm text-primary'>{message}</p>
      ) : null}
      {error ? (
        <p className='rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive'>{error}</p>
      ) : null}
      <div className='grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]'>
        <Card>
          <CardHeader>
            <CardTitle>{t('add')}</CardTitle>
          </CardHeader>
          <CardContent className='grid gap-3'>
            <div className='grid gap-2'>
              <Label>{t('titleLabel')}</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className='grid gap-2'>
              <Label>{t('authors')}</Label>
              <Input
                value={authors}
                onChange={(e) => setAuthors(e.target.value)}
                placeholder={t('authorsPlaceholder')}
              />
            </div>
            <div className='grid gap-2'>
              <Label>{t('doi')}</Label>
              <Input value={doi} onChange={(e) => setDoi(e.target.value)} />
            </div>
            <Button onClick={create} disabled={!projectId || !title.trim()}>
              {t('save')}
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t('bibliography')}</CardTitle>
          </CardHeader>
          <CardContent className='grid gap-4'>
            {items.length ? (
              items.map((item) => (
                <div key={item.id} className='grid gap-2 rounded-lg border p-3'>
                  <div className='font-medium'>{item.title}</div>
                  <div className='text-xs text-muted-foreground'>
                    {item.authors
                      .map(
                        (author) =>
                          author.literal ?? [author.given, author.family].filter(Boolean).join(' ')
                      )
                      .join(', ') || t('noAuthors')}
                    {item.publication_year ? ` · ${item.publication_year}` : ''}
                    {item.doi ? ` · ${item.doi}` : ''}
                  </div>
                  <div className='flex gap-2'>
                    <Input
                      value={claim}
                      onChange={(e) => setClaim(e.target.value)}
                      placeholder={t('recordClaimPlaceholder')}
                    />
                    <Button
                      size='sm'
                      onClick={() => createEvidence(item.id)}
                      disabled={!claim.trim()}
                    >
                      {t('record')}
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <p className='text-sm text-muted-foreground'>{t('noLiterature')}</p>
            )}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t('evidenceLog')}</CardTitle>
        </CardHeader>
        <CardContent>
          {evidence.length ? (
            <div className='divide-y'>
              {evidence.map((item) => (
                <div key={item.id} className='grid gap-1 py-3 text-sm'>
                  <div className='font-medium'>{item.claim_text}</div>
                  <div className='text-xs text-muted-foreground'>
                    {item.source_type} · <StatusBadge status={item.status} />
                    {item.locator ? ` · ${item.locator}` : ''}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className='text-sm text-muted-foreground'>{t('noEvidence')}</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
