'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import type { ResearchObject } from '@/lib/domain';
import { generateProjectAvatar, validateProjectLabel } from './project-avatar';
import { useProjectScope } from './project-scope-context';

export function ProjectLabelDialog({
  project,
  open,
  onOpenChange
}: {
  project: ResearchObject | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations('ProjectSwitcher');
  const { getProjectLabel, setProjectLabel } = useProjectScope();
  const [value, setValue] = useState('');
  const [touched, setTouched] = useState(false);
  const validation = validateProjectLabel(value);
  useEffect(() => {
    if (!open) return;
    setValue(project ? (getProjectLabel(project.id) ?? '') : '');
    setTouched(false);
  }, [getProjectLabel, open, project]);

  if (!project) return null;
  const currentProject = project;
  const preview =
    validation.valid && value
      ? validation.value
      : generateProjectAvatar(project.title, project.code);

  function save() {
    setTouched(true);
    if (!validation.valid) return;
    setProjectLabel(currentProject.id, validation.value || null);
    onOpenChange(false);
  }

  function reset() {
    setProjectLabel(currentProject.id, null);
    setValue('');
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='sm:max-w-sm'>
        <DialogHeader>
          <DialogTitle>{t('editLabel')}</DialogTitle>
        </DialogHeader>
        <div className='grid gap-4'>
          <div className='flex items-center gap-3 rounded-lg border bg-muted/30 p-3'>
            <span className='flex size-12 items-center justify-center rounded-xl bg-primary text-lg font-semibold text-primary-foreground'>
              {preview}
            </span>
            <div className='min-w-0'>
              <p className='truncate font-medium'>{currentProject.title}</p>
              <p className='font-mono text-xs text-muted-foreground'>{currentProject.code}</p>
            </div>
          </div>
          <label className='grid gap-1.5 text-sm font-medium'>
            {t('customLabel')}
            <Input
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
                setTouched(true);
              }}
              placeholder={generateProjectAvatar(currentProject.title, currentProject.code)}
              maxLength={5}
              aria-invalid={touched && !validation.valid}
            />
          </label>
          {touched && !validation.valid && (
            <p className='text-xs text-destructive' role='alert'>
              {t('labelError')}
            </p>
          )}
          <p className='text-xs text-muted-foreground'>{t('labelHint')}</p>
        </div>
        <DialogFooter>
          <Button type='button' variant='ghost' onClick={reset}>
            {t('resetLabel')}
          </Button>
          <Button type='button' onClick={save}>
            {t('save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
