'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api-client';
import type { ExperimentPrefill, ExperimentTemplate, JsonObject } from '@/lib/domain';
import { BackLink, PageHeader, StatusBadge } from './shared';
import { StructuredForm } from './structured-form';

export function ExperimentCreate({ projectId }: { projectId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const findingId = searchParams.get('finding_id');
  const t = useTranslations('Experiments');
  const statusT = useTranslations('Status');
  const [templates, setTemplates] = useState<ExperimentTemplate[]>([]);
  const [title, setTitle] = useState('');
  const [objective, setObjective] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [status, setStatus] = useState('draft');
  const [structured, setStructured] = useState<JsonObject>({});
  const [prefill, setPrefill] = useState<ExperimentPrefill | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    Promise.all([
      api.listTemplates(),
      findingId ? api.getSuggestedExperimentPrefill(findingId) : Promise.resolve(null)
    ])
      .then(([items, suggestion]) => {
        setTemplates(items);
        setPrefill(suggestion);
        setTemplateId(suggestion?.template_id ?? items[0]?.id ?? '');
        setTitle(suggestion?.title ?? '');
        setObjective(suggestion?.objective ?? '');
        setStructured(suggestion?.structured_data ?? {});
      })
      .catch((e) => setError(e.message));
  }, [findingId]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const created = await api.createExperiment(projectId, {
        title,
        objective,
        template_id: templateId,
        status,
        structured_data: structured,
        ...(prefill
          ? {
              suggestion_origin: {
                finding_id: prefill.finding_id,
                analysis_run_id: prefill.analysis_run_id,
                enabling_review_decision_id: prefill.enabling_review_decision_id,
                suggestion_hash: prefill.suggestion_hash,
                template_id: prefill.template_id,
                template_version: prefill.template_version,
                parent_experiment_id: prefill.parent_experiment_id
              }
            }
          : {})
      });
      router.push(`/dashboard/experiments/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorCreate'));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className='flex flex-1 flex-col px-4 pt-3 pb-8 md:px-6'>
      <BackLink href={`/dashboard/projects/${projectId}`} children={t('project')} />
      <PageHeader
        title={t('new')}
        description={prefill ? t('descriptionPrefill') : t('descriptionNew')}
      />
      <Card className='max-w-2xl'>
        <CardHeader>
          <CardTitle>{t('metadata')}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className='grid gap-4'>
            <div className='grid gap-2'>
              <Label htmlFor='experiment-title'>{t('titleLabel')}</Label>
              <Input
                id='experiment-title'
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t('titlePlaceholder')}
              />
            </div>
            {prefill && (
              <div className='rounded-lg border border-dashed p-3 text-sm'>
                <p className='font-medium'>{t('gatedSuggestion')}</p>
                <p className='text-muted-foreground'>
                  {t('enablingReview')} #{prefill.review_sequence_number}{' '}
                  <StatusBadge status={prefill.review_decision} /> · {t('parentOrigin')}{' '}
                  {prefill.parent_experiment_id}
                </p>
                <p className='mt-1 text-muted-foreground'>{prefill.control_strategy}</p>
              </div>
            )}
            <div className='grid gap-2'>
              <Label htmlFor='experiment-template'>{t('template')}</Label>
              <select
                id='experiment-template'
                required
                className='h-8 rounded-lg border border-input bg-background px-2 text-sm'
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name} · v{template.version}
                  </option>
                ))}
              </select>
            </div>
            <div className='grid gap-2'>
              <Label>{t('structuredProperties')}</Label>
              <p className='text-xs leading-5 text-muted-foreground'>{t('structuredFormHint')}</p>
              {templates.find((template) => template.id === templateId) ? (
                <StructuredForm
                  schema={
                    templates.find((template) => template.id === templateId)?.json_schema ?? {}
                  }
                  uiSchema={templates.find((template) => template.id === templateId)?.ui_schema}
                  data={structured}
                  onChange={setStructured}
                />
              ) : (
                <p className='rounded-lg border border-dashed p-3 text-sm text-muted-foreground'>
                  {t('chooseTemplate')}
                </p>
              )}
            </div>
            <div className='grid gap-2'>
              <Label htmlFor='experiment-status'>{t('statusLabel')}</Label>
              <select
                id='experiment-status'
                className='h-8 rounded-lg border border-input bg-background px-2 text-sm'
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value='draft'>{statusT('draft')}</option>
                <option value='planned'>{statusT('planned')}</option>
                <option value='running'>{statusT('running')}</option>
              </select>
            </div>
            <div className='grid gap-2'>
              <Label htmlFor='experiment-objective'>{t('objective')}</Label>
              <Textarea
                id='experiment-objective'
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                placeholder={t('objectivePlaceholder')}
              />
            </div>
            {error && <p className='text-sm text-destructive'>{error}</p>}
            <Button type='submit' disabled={busy || !templateId}>
              {busy ? t('saving') : t('create')}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
