'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api-client';
import type {
  Attachment,
  Experiment,
  ExperimentTemplate,
  JsonObject,
  Revision
} from '@/lib/domain';
import { BackLink, formatBytes, formatDate, PageHeader, PageState, StatusBadge } from './shared';
import { StructuredForm } from './structured-form';

const RichNoteEditor = dynamic(
  () => import('./rich-note-editor').then((mod) => mod.RichNoteEditor),
  { ssr: false, loading: () => <div className='min-h-56 animate-pulse rounded-lg bg-muted' /> }
);
const defaultNote = [
  {
    type: 'heading',
    props: { level: 2 },
    content: [{ type: 'text', text: 'Experimental note', styles: {} }]
  },
  {
    type: 'paragraph',
    content: [
      { type: 'text', text: 'Record your method, observations, and decisions here.', styles: {} }
    ]
  }
];

export function ExperimentDetail({ experimentId }: { experimentId: string }) {
  const router = useRouter();
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [template, setTemplate] = useState<ExperimentTemplate | null>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [tab, setTab] = useState<'overview' | 'record' | 'files' | 'revisions'>('overview');
  const [title, setTitle] = useState('');
  const [objective, setObjective] = useState('');
  const [status, setStatus] = useState('draft');
  const [structured, setStructured] = useState<JsonObject>({});
  const [note, setNote] = useState<Array<Record<string, unknown>>>(defaultNote);
  const [selectedRevision, setSelectedRevision] = useState<Revision | null>(null);
  const [cloneTitle, setCloneTitle] = useState('');
  const [revisionNote, setRevisionNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setError('');
    try {
      const item = await api.getExperiment(experimentId);
      setExperiment(item);
      setTitle(item.title);
      setObjective(item.objective ?? '');
      setStatus(item.status);
      setStructured(item.structured_data);
      setNote(item.note_document.length ? item.note_document : defaultNote);
      const [t, a, r] = await Promise.all([
        api.getTemplate(item.template_id),
        api.listAttachments(item.id),
        api.listRevisions(item.id)
      ]);
      setTemplate(t);
      setAttachments(a);
      setRevisions(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load experiment.');
    }
  }, [experimentId]);
  useEffect(() => {
    void load();
  }, [load]);
  const schema = (template?.json_schema ?? {}) as JsonObject;
  const snapshot = selectedRevision?.snapshot_json as Record<string, unknown> | undefined;
  async function saveMetadata() {
    if (!experiment) return;
    setBusy(true);
    setMessage('');
    setError('');
    try {
      const updated = await api.updateExperiment(experiment.id, {
        title,
        objective,
        status: status as Experiment['status'],
        structured_data: structured
      });
      setExperiment(updated);
      setMessage('Saved changes.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save changes.');
    } finally {
      setBusy(false);
    }
  }
  async function saveNote() {
    if (!experiment) return;
    setBusy(true);
    setMessage('');
    try {
      const updated = await api.updateExperiment(experiment.id, { note_document: note });
      setExperiment(updated);
      setMessage('Note saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save note.');
    } finally {
      setBusy(false);
    }
  }
  async function clone() {
    if (!experiment || !cloneTitle.trim()) return;
    setBusy(true);
    try {
      const copy = await api.cloneExperiment(experiment.id, cloneTitle.trim());
      router.push(`/dashboard/experiments/${copy.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to clone experiment.');
    } finally {
      setBusy(false);
    }
  }
  async function createRevision() {
    if (!experiment) return;
    setBusy(true);
    try {
      const revision = await api.createRevision(experiment.id, revisionNote);
      setRevisions((items) => [revision, ...items]);
      setRevisionNote('');
      setMessage(`Revision ${revision.revision_number} created.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create revision.');
    } finally {
      setBusy(false);
    }
  }
  async function upload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !experiment) return;
    setBusy(true);
    try {
      const attachment = await api.uploadAttachment(experiment.id, file);
      setAttachments((items) => [attachment, ...items]);
      setMessage('Attachment uploaded.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to upload attachment.');
    } finally {
      setBusy(false);
      event.target.value = '';
    }
  }
  async function removeAttachment(id: string) {
    if (!window.confirm('Delete this attachment?')) return;
    try {
      await api.deleteAttachment(id);
      setAttachments((items) => items.filter((item) => item.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete attachment.');
    }
  }
  if (error && !experiment)
    return (
      <div className='flex flex-1 flex-col px-4 pt-4 md:px-6'>
        <PageState error={error} />
      </div>
    );
  if (!experiment)
    return (
      <div className='flex flex-1 flex-col px-4 pt-4 md:px-6'>
        <PageState loading />
      </div>
    );
  return (
    <div className='flex flex-1 flex-col px-4 pt-3 pb-8 md:px-6'>
      <BackLink href={`/dashboard/projects/${experiment.project_id}`} children='Project' />
      <PageHeader
        title={experiment.title}
        description={`${experiment.code} · template v${experiment.template_version}`}
        action={
          <div className='flex flex-wrap items-center gap-2'>
            <StatusBadge status={experiment.status} />
            <Input
              className='w-48'
              value={cloneTitle}
              onChange={(e) => setCloneTitle(e.target.value)}
              placeholder='Clone title'
            />
            <Button variant='outline' disabled={busy || !cloneTitle.trim()} onClick={clone}>
              Clone
            </Button>
          </div>
        }
      />
      <div className='mb-4 flex flex-wrap gap-1 border-b'>
        {(['overview', 'record', 'files', 'revisions'] as const).map((item) => (
          <Button
            key={item}
            variant={tab === item ? 'secondary' : 'ghost'}
            className='rounded-b-none capitalize'
            onClick={() => setTab(item)}
          >
            {item}
          </Button>
        ))}
      </div>
      {message && (
        <p className='mb-4 rounded-md bg-primary/10 px-3 py-2 text-sm text-primary'>{message}</p>
      )}
      {error && (
        <p className='mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive'>
          {error}
        </p>
      )}
      {tab === 'overview' && (
        <div className='grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]'>
          <Card>
            <CardHeader>
              <CardTitle>Experiment metadata</CardTitle>
            </CardHeader>
            <CardContent className='grid gap-4'>
              <div className='grid gap-2'>
                <Label htmlFor='detail-title'>Title</Label>
                <Input id='detail-title' value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div className='grid gap-2'>
                <Label htmlFor='detail-status'>Status</Label>
                <select
                  id='detail-status'
                  className='h-8 rounded-lg border border-input bg-background px-2 text-sm'
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value='draft'>Draft</option>
                  <option value='planned'>Planned</option>
                  <option value='running'>Running</option>
                  <option value='completed'>Completed</option>
                  <option value='cancelled'>Cancelled</option>
                </select>
              </div>
              <div className='grid gap-2'>
                <Label htmlFor='detail-objective'>Objective</Label>
                <Textarea
                  id='detail-objective'
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                />
              </div>
              <Button onClick={saveMetadata} disabled={busy}>
                {busy ? 'Saving…' : 'Save changes'}
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Structured properties</CardTitle>
            </CardHeader>
            <CardContent>
              <StructuredForm schema={schema} data={structured} onChange={setStructured} />
              <Button className='mt-4' onClick={saveMetadata} disabled={busy}>
                Save structured data
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
      {tab === 'record' && (
        <Card>
          <CardHeader>
            <CardTitle>Experimental note</CardTitle>
          </CardHeader>
          <CardContent>
            <RichNoteEditor initialContent={note} onChange={setNote} />
            <Button className='mt-4' onClick={saveNote} disabled={busy}>
              {busy ? 'Saving…' : 'Save note'}
            </Button>
          </CardContent>
        </Card>
      )}
      {tab === 'files' && (
        <Card>
          <CardHeader>
            <CardTitle>Attachments</CardTitle>
          </CardHeader>
          <CardContent className='grid gap-4'>
            <Input type='file' onChange={upload} disabled={busy} />
            {attachments.length === 0 ? (
              <p className='text-sm text-muted-foreground'>No files attached.</p>
            ) : (
              <ul className='divide-y rounded-lg border'>
                {attachments.map((file) => (
                  <li
                    key={file.id}
                    className='flex flex-wrap items-center justify-between gap-3 px-3 py-3 text-sm'
                  >
                    <div>
                      <a
                        className='font-medium hover:underline'
                        href={api.downloadUrl(file.id)}
                        target='_blank'
                        rel='noreferrer'
                      >
                        {file.original_filename}
                      </a>
                      <div className='text-xs text-muted-foreground'>
                        {formatBytes(file.size_bytes)} · {formatDate(file.created_at)}
                      </div>
                    </div>
                    <Button
                      variant='destructive'
                      size='sm'
                      onClick={() => removeAttachment(file.id)}
                    >
                      Delete
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
      {tab === 'revisions' && (
        <div className='grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]'>
          <Card>
            <CardHeader>
              <CardTitle>Create revision</CardTitle>
            </CardHeader>
            <CardContent className='grid gap-3'>
              <Input
                value={revisionNote}
                onChange={(e) => setRevisionNote(e.target.value)}
                placeholder='What changed?'
              />
              <Button onClick={createRevision} disabled={busy}>
                Create revision
              </Button>
              <div className='divide-y rounded-lg border'>
                {revisions.map((revision) => (
                  <button
                    type='button'
                    key={revision.id}
                    className='block w-full px-3 py-3 text-left text-sm hover:bg-muted'
                    onClick={() => setSelectedRevision(revision)}
                  >
                    <div className='flex justify-between'>
                      <span className='font-medium'>Revision {revision.revision_number}</span>
                      <span className='text-xs text-muted-foreground'>
                        {formatDate(revision.created_at)}
                      </span>
                    </div>
                    <div className='text-xs text-muted-foreground'>
                      {revision.change_note || 'No change note'}
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>
                {selectedRevision
                  ? `Revision ${selectedRevision.revision_number}`
                  : 'Select a revision'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedRevision ? (
                <div className='grid gap-4'>
                  <pre className='max-h-72 overflow-auto rounded-lg bg-muted p-3 text-xs'>
                    {JSON.stringify(snapshot, null, 2)}
                  </pre>
                  <RichNoteEditor
                    initialContent={
                      (snapshot?.note_document as Array<Record<string, unknown>>) || defaultNote
                    }
                    editable={false}
                    key={selectedRevision.id}
                  />
                </div>
              ) : (
                <p className='text-sm text-muted-foreground'>
                  Choose a revision to inspect its immutable snapshot.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
