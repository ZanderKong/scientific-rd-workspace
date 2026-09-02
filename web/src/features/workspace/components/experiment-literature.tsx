'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api-client';
import type { Experiment, Literature, LiteratureLink } from '@/lib/domain';
import { useTranslations } from 'next-intl';

export function ExperimentLiterature({ experiment }: { experiment: Experiment }) {
  const t = useTranslations('Literature');
  const [literature, setLiterature] = useState<Literature[]>([]);
  const [links, setLinks] = useState<LiteratureLink[]>([]);
  const [literatureId, setLiteratureId] = useState('');
  const [relationship, setRelationship] = useState('background');
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    const [items, linked] = await Promise.all([
      api.listLiterature(experiment.project_id),
      api.listLiteratureLinks(experiment.id)
    ]);
    setLiterature(items);
    setLinks(linked);
  }, [experiment.id, experiment.project_id]);
  useEffect(() => {
    void load().catch((e) => setError(e instanceof Error ? e.message : t('noLiterature')));
  }, [load, t]);
  async function link() {
    if (!literatureId) return;
    try {
      await api.createLiteratureLink(experiment.id, {
        literature_id: literatureId,
        relationship_type: relationship
      });
      setLiteratureId('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('noLiterature'));
    }
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('links')}</CardTitle>
      </CardHeader>
      <CardContent className='grid gap-4'>
        <div className='flex flex-wrap gap-2'>
          <select
            className='h-8 min-w-56 rounded-lg border bg-background px-2 text-sm'
            value={literatureId}
            onChange={(e) => setLiteratureId(e.target.value)}
          >
            <option value=''>{t('chooseRecord')}</option>
            {literature.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
          <select
            className='h-8 rounded-lg border bg-background px-2 text-sm'
            value={relationship}
            onChange={(e) => setRelationship(e.target.value)}
          >
            <option value='background'>{t('background')}</option>
            <option value='method'>{t('method')}</option>
            <option value='comparison'>{t('comparison')}</option>
            <option value='supporting'>{t('supporting')}</option>
            <option value='contradicting'>{t('contradicting')}</option>
          </select>
          <Button onClick={link} disabled={!literatureId}>
            {t('link')}
          </Button>
        </div>
        {error ? <p className='text-sm text-destructive'>{error}</p> : null}
        {links.length ? (
          <div className='divide-y rounded-lg border'>
            {links.map((item) => (
              <div key={item.id} className='px-3 py-2 text-sm'>
                <div className='font-medium'>{item.literature?.title ?? item.literature_id}</div>
                <div className='text-xs text-muted-foreground'>{item.relationship_type}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className='text-sm text-muted-foreground'>{t('noLinked')}</p>
        )}
      </CardContent>
    </Card>
  );
}
