'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type { Project } from '@/lib/domain';
import { api } from '@/lib/api-client';

export function ProjectForm({
  project,
  onSaved,
  onCancel
}: {
  project?: Project;
  onSaved: (project: Project) => void;
  onCancel?: () => void;
}) {
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
      setError(err instanceof Error ? err.message : 'Unable to save project.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className='grid gap-4'>
      <div className='grid gap-2'>
        <Label htmlFor='project-title'>Title</Label>
        <Input
          id='project-title'
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder='e.g. Polymer formulation screening'
        />
      </div>
      <div className='grid gap-2'>
        <Label htmlFor='project-description'>Description</Label>
        <Textarea
          id='project-description'
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder='What question is this project answering?'
        />
      </div>
      <div className='grid gap-2'>
        <Label htmlFor='project-status'>Status</Label>
        <select
          id='project-status'
          className='h-8 rounded-lg border border-input bg-background px-2 text-sm'
          value={status}
          onChange={(e) => setStatus(e.target.value as Project['status'])}
        >
          <option value='active'>Active</option>
          <option value='paused'>Paused</option>
          <option value='completed'>Completed</option>
          <option value='archived'>Archived</option>
        </select>
      </div>
      {error && <p className='text-sm text-destructive'>{error}</p>}
      <div className='flex justify-end gap-2'>
        {onCancel && (
          <Button type='button' variant='ghost' onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type='submit' disabled={busy}>
          {busy ? 'Saving…' : project ? 'Save project' : 'Create project'}
        </Button>
      </div>
    </form>
  );
}
