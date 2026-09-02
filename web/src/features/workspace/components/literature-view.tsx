'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { api } from '@/lib/api-client';
import type { Evidence, Literature, Project } from '@/lib/domain';
import { formatDate, PageHeader, PageState, StatusBadge } from './shared';
import { SectionHeader } from './scientific-ui';
import { useLocale, useTranslations } from 'next-intl';
import { parseLocale } from '@/i18n/config';

export function LiteratureView() {
  const locale = parseLocale(useLocale());
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
  const [addOpen, setAddOpen] = useState(false);
  const [evidenceTarget, setEvidenceTarget] = useState<Literature | null>(null);
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
      setAddOpen(false);
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
      setEvidenceTarget(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('noEvidence'));
    }
  }
  if (error && !projects.length) return <PageState error={error} />;
  return (
    <div className='flex flex-1 flex-col gap-6 px-4 pt-4 pb-8 md:px-6'>
      <PageHeader title={t('title')} description={t('description')} />
      <div className='flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-muted/20 p-3'>
        <select
          className='h-9 min-w-64 rounded-lg border bg-background px-3 text-sm'
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          aria-label={common('chooseProject')}
        >
          <option value=''>{common('chooseProject')}</option>
          {projects.map((item) => (
            <option key={item.id} value={item.id}>
              {item.code} · {item.title}
            </option>
          ))}
        </select>
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogTrigger render={<Button>{t('add')}</Button>} />
          <DialogContent className='sm:max-w-lg'>
            <DialogHeader>
              <DialogTitle>{t('add')}</DialogTitle>
              <DialogDescription>{t('addHint')}</DialogDescription>
            </DialogHeader>
            <div className='grid gap-3'>
              <div className='grid gap-2'>
                <Label htmlFor='literature-title'>{t('titleLabel')}</Label>
                <Input
                  id='literature-title'
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>
              <div className='grid gap-2'>
                <Label htmlFor='literature-authors'>{t('authors')}</Label>
                <Input
                  id='literature-authors'
                  value={authors}
                  onChange={(e) => setAuthors(e.target.value)}
                  placeholder={t('authorsPlaceholder')}
                />
              </div>
              <div className='grid gap-2'>
                <Label htmlFor='literature-doi'>{t('doi')}</Label>
                <Input id='literature-doi' value={doi} onChange={(e) => setDoi(e.target.value)} />
              </div>
            </div>
            <DialogFooter>
              <Button onClick={() => void create()} disabled={!projectId || !title.trim()}>
                {t('save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      {message ? (
        <p className='rounded-md bg-primary/10 px-3 py-2 text-sm text-primary'>{message}</p>
      ) : null}
      {error ? (
        <p className='rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive'>{error}</p>
      ) : null}
      <Card>
        <CardHeader>
          <SectionHeader title={t('bibliography')} description={t('bibliographyHint')} />
        </CardHeader>
        <CardContent className='p-0'>
          {items.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('source')}</TableHead>
                  <TableHead>{t('authors')}</TableHead>
                  <TableHead>{t('published')}</TableHead>
                  <TableHead>{t('doi')}</TableHead>
                  <TableHead className='text-right'>{t('evidenceAction')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className='min-w-72 whitespace-normal'>
                      <div className='font-medium'>{item.title}</div>
                      <div className='mt-1 font-mono text-[0.68rem] text-muted-foreground'>
                        {item.id}
                      </div>
                    </TableCell>
                    <TableCell className='max-w-56 whitespace-normal text-sm'>
                      {item.authors
                        .map(
                          (author) =>
                            author.literal ??
                            [author.given, author.family].filter(Boolean).join(' ')
                        )
                        .join(', ') || t('noAuthors')}
                    </TableCell>
                    <TableCell className='text-sm tabular-nums'>
                      {item.publication_year ?? '—'}
                    </TableCell>
                    <TableCell className='font-mono text-xs'>{item.doi ?? '—'}</TableCell>
                    <TableCell className='text-right'>
                      <Button
                        variant='outline'
                        size='sm'
                        onClick={() => {
                          setEvidenceTarget(item);
                          setClaim('');
                        }}
                      >
                        {t('record')}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className='p-6 text-sm text-muted-foreground'>{t('noLiterature')}</p>
          )}
        </CardContent>
      </Card>
      <Dialog
        open={Boolean(evidenceTarget)}
        onOpenChange={(open) => {
          if (!open) setEvidenceTarget(null);
        }}
      >
        <DialogContent className='sm:max-w-lg'>
          <DialogHeader>
            <DialogTitle>{t('record')}</DialogTitle>
            <DialogDescription>{evidenceTarget?.title}</DialogDescription>
          </DialogHeader>
          <div className='grid gap-2'>
            <Label htmlFor='evidence-claim'>{t('recordClaimPlaceholder')}</Label>
            <Input id='evidence-claim' value={claim} onChange={(e) => setClaim(e.target.value)} />
          </div>
          <DialogFooter>
            <Button
              onClick={() => {
                if (evidenceTarget) void createEvidence(evidenceTarget.id);
              }}
              disabled={!claim.trim()}
            >
              {t('saveEvidence')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Card>
        <CardHeader>
          <SectionHeader title={t('evidenceLog')} description={t('evidenceHint')} />
        </CardHeader>
        <CardContent>
          {evidence.length ? (
            <div className='divide-y'>
              {evidence.map((item) => (
                <div key={item.id} className='grid gap-1 py-3 text-sm'>
                  <div className='font-medium'>{item.claim_text}</div>
                  <div className='text-xs text-muted-foreground'>
                    {item.source_type} · <StatusBadge status={item.status} /> ·{' '}
                    {formatDate(item.created_at, locale)}
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
