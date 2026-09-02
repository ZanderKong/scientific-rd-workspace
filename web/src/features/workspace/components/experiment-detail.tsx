'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
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
  ExperimentProvenance,
  JsonObject,
  Revision
} from '@/lib/domain';
import { parseRevisionSnapshot } from '@/lib/revision-snapshot';
import { BackLink, formatBytes, formatDate, PageHeader, PageState, StatusBadge } from './shared';
import { StructuredForm } from './structured-form';
import { MeasurementData } from './measurement-data';
import { ExperimentLiterature } from './experiment-literature';
import { parseLocale } from '@/i18n/config';
import { ProvenanceSummary, TechnicalDetails, TraceabilityTimeline } from './scientific-ui';

const RichNoteEditor = dynamic(
  () => import('./rich-note-editor').then((mod) => mod.RichNoteEditor),
  { ssr: false, loading: () => <div className='min-h-56 animate-pulse rounded-lg bg-muted' /> }
);
function createDefaultNote(title: string, placeholder: string) {
  return [
    {
      type: 'heading',
      props: { level: 2 },
      content: [{ type: 'text', text: title, styles: {} }]
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: placeholder, styles: {} }]
    }
  ];
}

export function ExperimentDetail({ experimentId }: { experimentId: string }) {
  const router = useRouter();
  const locale = parseLocale(useLocale());
  const t = useTranslations('Experiments');
  const statusT = useTranslations('Status');
  const defaultNote = useMemo(() => createDefaultNote(t('note'), t('notePlaceholder')), [t]);
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [template, setTemplate] = useState<ExperimentTemplate | null>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [provenance, setProvenance] = useState<ExperimentProvenance | null>(null);
  const [tab, setTab] = useState<
    'overview' | 'record' | 'files' | 'data' | 'literature' | 'revisions'
  >('overview');
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
      try {
        setProvenance(await api.getExperimentProvenance(item.id));
      } catch {
        setProvenance(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorLoad'));
    }
  }, [defaultNote, experimentId, t]);
  useEffect(() => {
    void load();
  }, [load]);
  const schema = (template?.json_schema ?? {}) as JsonObject;
  const snapshot = selectedRevision ? parseRevisionSnapshot(selectedRevision.snapshot_json) : null;
  const snapshotUsesLoadedTemplate =
    snapshot !== null &&
    template?.id === snapshot.experiment.template_id &&
    template.version === snapshot.experiment.template_version;
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
      setMessage(t('savedChanges'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorLoad'));
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
      setMessage(t('savedChanges'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorLoad'));
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
      setError(err instanceof Error ? err.message : t('errorLoad'));
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
      setMessage(t('revisionCreated', { number: revision.revision_number }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorLoad'));
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
      setMessage(t('attachmentUploaded'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorLoad'));
    } finally {
      setBusy(false);
      event.target.value = '';
    }
  }
  async function removeAttachment(id: string) {
    if (!window.confirm(t('confirmDeleteAttachment'))) return;
    try {
      await api.deleteAttachment(id);
      setAttachments((items) => items.filter((item) => item.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('errorLoad'));
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
  const traceNodes = [
    { id: experiment.id, kind: 'experiment', label: experiment.code, detail: experiment.title },
    ...(experiment.parent_experiment_id
      ? [
          {
            id: experiment.parent_experiment_id,
            kind: 'parent experiment',
            label: experiment.parent_experiment_id,
            href: `/dashboard/experiments/${experiment.parent_experiment_id}`
          }
        ]
      : []),
    ...revisions.slice(0, 3).map((revision) => ({
      id: revision.id,
      kind: 'revision',
      label: t('revisionLabel', { number: revision.revision_number }),
      detail: revision.change_note || t('noChangeNote')
    })),
    ...attachments.slice(0, 3).map((attachment) => ({
      id: attachment.id,
      kind: 'attachment',
      label: attachment.original_filename,
      detail: `${formatBytes(attachment.size_bytes, locale)} · ${attachment.sha256}`
    })),
    ...(provenance
      ? [
          {
            id: provenance.finding_id,
            kind: 'finding',
            label: provenance.finding_id,
            href: `/dashboard/analysis/${provenance.analysis_run_id}`,
            detail: t('gatedSuggestion')
          }
        ]
      : [])
  ];
  return (
    <div className='mx-auto flex w-full max-w-[1440px] flex-1 flex-col px-4 pt-3 pb-8 md:px-6'>
      <BackLink href={`/dashboard/projects/${experiment.project_id}`} children={t('project')} />
      <PageHeader
        title={experiment.title}
        description={`${experiment.code} · ${t('templateVersion', { version: experiment.template_version })}`}
        action={
          <div className='flex flex-wrap items-center gap-2'>
            <StatusBadge status={experiment.status} />
            <Input
              className='w-48'
              value={cloneTitle}
              onChange={(e) => setCloneTitle(e.target.value)}
              placeholder={t('cloneTitle')}
            />
            <Button variant='outline' disabled={busy || !cloneTitle.trim()} onClick={clone}>
              {t('clone')}
            </Button>
          </div>
        }
      />
      <div className='mb-5 flex gap-1 overflow-x-auto border-b' role='tablist'>
        {(['overview', 'record', 'files', 'data', 'literature', 'revisions'] as const).map(
          (item) => (
            <Button
              key={item}
              variant={tab === item ? 'secondary' : 'ghost'}
              className='shrink-0 rounded-b-none'
              role='tab'
              aria-selected={tab === item}
              onClick={() => setTab(item)}
            >
              {t(item)}
            </Button>
          )
        )}
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
        <div className='grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]'>
          <Card>
            <CardHeader>
              <CardTitle>{t('metadata')}</CardTitle>
            </CardHeader>
            <CardContent className='grid gap-4'>
              <div className='grid gap-2'>
                <Label htmlFor='detail-title'>{t('titleLabel')}</Label>
                <Input id='detail-title' value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div className='grid gap-2'>
                <Label htmlFor='detail-status'>{t('statusLabel')}</Label>
                <select
                  id='detail-status'
                  className='h-8 rounded-lg border border-input bg-background px-2 text-sm'
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value='draft'>{statusT('draft')}</option>
                  <option value='planned'>{statusT('planned')}</option>
                  <option value='running'>{statusT('running')}</option>
                  <option value='completed'>{statusT('completed')}</option>
                  <option value='cancelled'>{statusT('cancelled')}</option>
                </select>
              </div>
              <div className='grid gap-2'>
                <Label htmlFor='detail-objective'>{t('objective')}</Label>
                <Textarea
                  id='detail-objective'
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                />
              </div>
              <Button onClick={saveMetadata} disabled={busy}>
                {busy ? t('saving') : t('saveChanges')}
              </Button>
            </CardContent>
          </Card>
          {provenance ? (
            <ProvenanceSummary
              title={t('creationProvenance')}
              items={[
                {
                  label: t('finding'),
                  value: provenance.finding_id,
                  href: `/dashboard/analysis/${provenance.analysis_run_id}`
                },
                {
                  label: t('analysisRun'),
                  value: provenance.analysis_run_id,
                  href: `/dashboard/analysis/${provenance.analysis_run_id}`
                },
                { label: t('enablingReview'), value: provenance.enabling_review_decision_id },
                { label: t('relationType'), value: provenance.relation_type },
                { label: t('createdAt'), value: formatDate(provenance.created_at, locale) }
              ]}
              note={
                <TechnicalDetails title={t('immutableSnapshots')}>
                  <pre className='max-h-72 overflow-auto rounded bg-muted p-3 font-mono text-xs'>
                    {JSON.stringify(
                      {
                        suggestion: provenance.suggestion_snapshot_json,
                        submitted_values: provenance.submitted_values_snapshot_json
                      },
                      null,
                      2
                    )}
                  </pre>
                </TechnicalDetails>
              }
            />
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>{t('structuredProperties')}</CardTitle>
            </CardHeader>
            <CardContent>
              <StructuredForm
                schema={schema}
                uiSchema={template?.ui_schema}
                data={structured}
                onChange={setStructured}
              />
              <Button className='mt-4' onClick={saveMetadata} disabled={busy}>
                {t('saveStructuredData')}
              </Button>
            </CardContent>
          </Card>
          <TraceabilityTimeline title={t('traceability')} nodes={traceNodes} />
        </div>
      )}
      {tab === 'record' && (
        <Card>
          <CardHeader>
            <CardTitle>{t('note')}</CardTitle>
          </CardHeader>
          <CardContent>
            <RichNoteEditor initialContent={note} onChange={setNote} key={locale} />
            <Button className='mt-4' onClick={saveNote} disabled={busy}>
              {busy ? t('saving') : t('saveNote')}
            </Button>
          </CardContent>
        </Card>
      )}
      {tab === 'files' && (
        <Card>
          <CardHeader>
            <CardTitle>{t('attachments')}</CardTitle>
          </CardHeader>
          <CardContent className='grid gap-4'>
            <Input type='file' onChange={upload} disabled={busy} aria-label={t('upload')} />
            {attachments.length === 0 ? (
              <p className='text-sm text-muted-foreground'>{t('noFiles')}</p>
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
                        {formatBytes(file.size_bytes, locale)} ·{' '}
                        {formatDate(file.created_at, locale)}
                      </div>
                    </div>
                    <Button
                      variant='destructive'
                      size='sm'
                      onClick={() => removeAttachment(file.id)}
                    >
                      {t('deleteAttachment')}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
      {tab === 'data' && (
        <MeasurementData
          experiment={experiment}
          attachments={attachments}
          onMessage={(text, isError) => {
            if (isError) setError(text);
            else setMessage(text);
          }}
        />
      )}
      {tab === 'literature' && <ExperimentLiterature experiment={experiment} />}
      {tab === 'revisions' && (
        <div className='grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]'>
          <Card>
            <CardHeader>
              <CardTitle>{t('revisionCreate')}</CardTitle>
            </CardHeader>
            <CardContent className='grid gap-3'>
              <Input
                value={revisionNote}
                onChange={(e) => setRevisionNote(e.target.value)}
                placeholder={t('revisionPlaceholder')}
              />
              <Button onClick={createRevision} disabled={busy}>
                {t('revisionCreateAction')}
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
                      <span className='font-medium'>
                        {t('revisionLabel', { number: revision.revision_number })}
                      </span>
                      <span className='text-xs text-muted-foreground'>
                        {formatDate(revision.created_at, locale)}
                      </span>
                    </div>
                    <div className='text-xs text-muted-foreground'>
                      {revision.change_note || t('noChangeNote')}
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
                  ? t('revisionLabel', { number: selectedRevision.revision_number })
                  : t('selectRevision')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {selectedRevision ? (
                snapshot ? (
                  <div className='grid gap-6'>
                    <div className='grid gap-1 rounded-lg border p-4 text-sm'>
                      <div className='flex flex-wrap items-center justify-between gap-2'>
                        <span className='font-medium'>{snapshot.experiment.title}</span>
                        <StatusBadge status={snapshot.experiment.status} />
                      </div>
                      <p className='text-muted-foreground'>
                        {t('templateVersion', { version: snapshot.experiment.template_version })}
                      </p>
                      {snapshot.experiment.objective ? (
                        <p>{snapshot.experiment.objective}</p>
                      ) : null}
                    </div>

                    <section className='grid gap-2'>
                      <h3 className='text-sm font-medium'>{t('structuredProperties')}</h3>
                      {snapshotUsesLoadedTemplate ? (
                        <StructuredForm
                          schema={schema}
                          uiSchema={template?.ui_schema}
                          data={snapshot.experiment.structured_data}
                          readonly
                        />
                      ) : (
                        <p className='rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive'>
                          {t('exactTemplateMissing')}
                        </p>
                      )}
                    </section>

                    <section className='grid gap-2'>
                      <h3 className='text-sm font-medium'>{t('note')}</h3>
                      {snapshot.experiment.note_document.length > 0 ? (
                        <RichNoteEditor
                          initialContent={snapshot.experiment.note_document}
                          editable={false}
                          key={selectedRevision.id}
                        />
                      ) : (
                        <p className='text-sm text-muted-foreground'>{t('noNote')}</p>
                      )}
                    </section>

                    <section className='grid gap-2'>
                      <h3 className='text-sm font-medium'>{t('attachmentMetadata')}</h3>
                      {snapshot.attachments.length > 0 ? (
                        <ul className='divide-y rounded-lg border text-sm'>
                          {snapshot.attachments.map((attachment) => (
                            <li key={attachment.id} className='grid gap-1 px-3 py-2'>
                              <span className='font-medium'>{attachment.original_filename}</span>
                              <span className='text-xs text-muted-foreground'>
                                {formatBytes(attachment.size_bytes, locale)} · {t('sha256')}{' '}
                                {attachment.sha256}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className='text-sm text-muted-foreground'>
                          {t('noAttachmentsSnapshot')}
                        </p>
                      )}
                    </section>

                    {snapshot.measurements?.length ? (
                      <section className='grid gap-2'>
                        <h3 className='text-sm font-medium'>{t('measurementReferences')}</h3>
                        <ul className='divide-y rounded-lg border text-sm'>
                          {snapshot.measurements.map((measurement) => (
                            <li key={measurement.id} className='grid gap-1 px-3 py-2'>
                              <span className='font-medium'>{measurement.name}</span>
                              <span className='text-xs text-muted-foreground'>
                                {t('rowCount', { count: measurement.row_count })} ·{' '}
                                {measurement.x_label} ({measurement.x_unit}) → {measurement.y_label}{' '}
                                ({measurement.y_unit})
                              </span>
                              <span className='text-xs text-muted-foreground'>
                                {t('immutablePoints')} {t('sha256')} {measurement.points_sha256}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}

                    {snapshot.literature_links?.length ? (
                      <section className='grid gap-2'>
                        <h3 className='text-sm font-medium'>{t('literatureReferences')}</h3>
                        <ul className='divide-y rounded-lg border text-sm'>
                          {snapshot.literature_links.map((link) => (
                            <li key={link.id} className='grid gap-1 px-3 py-2'>
                              <span className='font-medium'>{link.title}</span>
                              <span className='text-xs text-muted-foreground'>
                                {link.relationship_type} · {t('literature')} {link.literature_id}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}

                    {snapshot.evidence?.length ? (
                      <section className='grid gap-2'>
                        <h3 className='text-sm font-medium'>{t('evidenceReferences')}</h3>
                        <ul className='divide-y rounded-lg border text-sm'>
                          {snapshot.evidence.map((item) => (
                            <li key={item.id} className='grid gap-1 px-3 py-2'>
                              <span className='font-medium'>{item.claim_text}</span>
                              <span className='text-xs text-muted-foreground'>
                                {item.stance} · {item.source_type} ·{' '}
                                <StatusBadge status={item.status} />
                              </span>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}

                    <details className='rounded-lg border p-3 text-xs'>
                      <summary className='cursor-pointer font-medium'>{t('rawSnapshot')}</summary>
                      <pre className='mt-3 max-h-72 overflow-auto rounded-lg bg-muted p-3'>
                        {JSON.stringify(selectedRevision.snapshot_json, null, 2)}
                      </pre>
                    </details>
                  </div>
                ) : (
                  <p className='text-sm text-destructive'>{t('malformedSnapshot')}</p>
                )
              ) : (
                <p className='text-sm text-muted-foreground'>{t('chooseRevision')}</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
