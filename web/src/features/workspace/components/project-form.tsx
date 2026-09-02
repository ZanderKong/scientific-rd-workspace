'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type { Project } from '@/lib/domain';
import { api } from '@/lib/api-client';
import { useTranslations } from 'next-intl';

export function ProjectForm({
  project,
  onSaved,
  onCancel
}: {
  project?: Project;
  onSaved: (project: Project) => void;
  onCancel?: () => void;
}) {
  const t = useTranslations('Projects');
  const statusT = useTranslations('Status');
  const [title, setTitle] = useState(project?.title ?? '');
  const [description, setDescription] = useState(project?.description ?? '');
  const [status, setStatus] = useState(project?.status ?? 'active');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const saved = project
        ? await api.updateProject(project.id, { title, description, status })
        : await api.createProject({ title, description, status });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorSave'));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className='grid gap-4'>
      <div className='grid gap-2'>
        <Label htmlFor='project-title'>{t('titleLabel')}</Label>
        <Input
          id='project-title'
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t('titlePlaceholder')}
        />
      </div>
      <div className='grid gap-2'>
        <Label htmlFor='project-description'>{t('descriptionLabel')}</Label>
        <Textarea
          id='project-description'
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t('descriptionPlaceholder')}
        />
      </div>
      <div className='grid gap-2'>
        <Label htmlFor='project-status'>{t('statusLabel')}</Label>
        <select
          id='project-status'
          className='h-8 rounded-lg border border-input bg-background px-2 text-sm'
          value={status}
          onChange={(e) => setStatus(e.target.value as Project['status'])}
        >
          <option value='active'>{statusT('active')}</option>
          <option value='paused'>{statusT('paused')}</option>
          <option value='completed'>{statusT('completed')}</option>
          <option value='archived'>{statusT('archived')}</option>
        </select>
      </div>
      {error && <p className='text-sm text-destructive'>{error}</p>}
      <div className='flex justify-end gap-2'>
        {onCancel && (
          <Button type='button' variant='ghost' onClick={onCancel}>
            {t('cancel')}
          </Button>
        )}
        <Button type='submit' disabled={busy}>
          {busy ? t('saving') : project ? t('save') : t('create')}
        </Button>
      </div>
    </form>
  );
}
