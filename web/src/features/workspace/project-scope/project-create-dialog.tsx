'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { api, ApiError } from '@/lib/api-client';
import { useProjectScope } from './project-scope-context';

function readableError(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : 'Request failed';
}

export function ProjectCreateDialog({
  open,
  onOpenChange
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations('ProjectSwitcher');
  const { registerCreatedProject } = useProjectScope();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [code, setCode] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    if (!saving) onOpenChange(false);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const result = await api.createProjectRecord(
        {
          project: {
            title: title.trim(),
            code: code.trim() || undefined,
            status: 'active',
            properties_jsonb: description.trim() ? { description: description.trim() } : {}
          }
        },
        globalThis.crypto?.randomUUID?.()
      );
      registerCreatedProject(result.project);
      setTitle('');
      setDescription('');
      setCode('');
      onOpenChange(false);
    } catch (cause) {
      setError(readableError(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !saving && onOpenChange(next)}>
      <DialogContent className='sm:max-w-lg'>
        <DialogHeader>
          <DialogTitle>{t('createTitle')}</DialogTitle>
          <DialogDescription>{t('createDescription')}</DialogDescription>
        </DialogHeader>
        <form className='grid gap-4' onSubmit={submit}>
          <label className='grid gap-1.5 text-sm font-medium'>
            {t('projectName')} *
            <Input
              autoFocus
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={t('projectNamePlaceholder')}
            />
          </label>
          <label className='grid gap-1.5 text-sm font-medium'>
            {t('description')}{' '}
            <span className='text-xs font-normal text-muted-foreground'>({t('optional')})</span>
            <Textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={t('descriptionPlaceholder')}
              rows={3}
            />
          </label>
          <label className='grid gap-1.5 text-sm font-medium'>
            {t('projectCode')}{' '}
            <span className='text-xs font-normal text-muted-foreground'>({t('optional')})</span>
            <Input
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder={t('projectCodePlaceholder')}
            />
          </label>
          {error && (
            <p className='text-sm text-destructive' role='alert'>
              {error}
            </p>
          )}
          <DialogFooter>
            <Button type='button' variant='outline' onClick={close}>
              {t('cancel')}
            </Button>
            <Button type='submit' disabled={saving || !title.trim()}>
              {saving ? t('saving') : t('create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
