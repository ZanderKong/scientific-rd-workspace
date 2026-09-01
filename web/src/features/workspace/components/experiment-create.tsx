'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api-client';
import type { ExperimentTemplate } from '@/lib/domain';
import { BackLink, PageHeader } from './shared';

export function ExperimentCreate({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [templates, setTemplates] = useState<ExperimentTemplate[]>([]);
  const [title, setTitle] = useState('');
  const [objective, setObjective] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [status, setStatus] = useState('draft');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    api
      .listTemplates()
      .then((items) => {
        setTemplates(items);
        setTemplateId(items[0]?.id ?? '');
      })
      .catch((e) => setError(e.message));
  }, []);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const created = await api.createExperiment(projectId, {
        title,
        objective,
        template_id: templateId,
        status
      });
      router.push(`/dashboard/experiments/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create experiment.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className='flex flex-1 flex-col px-4 pt-3 pb-8 md:px-6'>
      <BackLink href={`/dashboard/projects/${projectId}`} children='Project' />
      <PageHeader
        title='New experiment'
        description='Start with a template, then refine the record in the experiment workspace.'
      />
      <Card className='max-w-2xl'>
        <CardHeader>
          <CardTitle>Experiment metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className='grid gap-4'>
            <div className='grid gap-2'>
              <Label htmlFor='experiment-title'>Title</Label>
              <Input
                id='experiment-title'
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder='e.g. 2% PVA film, 80°C dry'
              />
            </div>
            <div className='grid gap-2'>
              <Label htmlFor='experiment-template'>Template</Label>
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
              <Label htmlFor='experiment-status'>Status</Label>
              <select
                id='experiment-status'
                className='h-8 rounded-lg border border-input bg-background px-2 text-sm'
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value='draft'>Draft</option>
                <option value='planned'>Planned</option>
                <option value='running'>Running</option>
              </select>
            </div>
            <div className='grid gap-2'>
              <Label htmlFor='experiment-objective'>Objective</Label>
              <Textarea
                id='experiment-objective'
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                placeholder='What are you testing?'
              />
            </div>
            {error && <p className='text-sm text-destructive'>{error}</p>}
            <Button type='submit' disabled={busy || !templateId}>
              {busy ? 'Creating…' : 'Create experiment'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
