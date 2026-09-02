'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { ChartContainer } from '@/components/ui/chart';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { api } from '@/lib/api-client';
import type {
  CompareResult,
  Experiment,
  MeasurementPoint,
  Project,
  ModelProfile,
  Revision,
  Literature,
  Evidence
} from '@/lib/domain';
import { useTranslations } from 'next-intl';
import { PageHeader, PageState, StatusBadge } from './shared';
import { formatStructuredValue, toggleBoundedSelection } from '../presentation';
import { MetadataList, MetricStrip, SectionHeader, TechnicalDetails } from './scientific-ui';

export function CompareView() {
  const router = useRouter();
  const t = useTranslations('Compare');
  const common = useTranslations('Common');
  const [projects, setProjects] = useState<Project[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [projectId, setProjectId] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [points, setPoints] = useState<Record<string, MeasurementPoint[]>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [profileKey, setProfileKey] = useState('analysis-default');
  const [revisions, setRevisions] = useState<Record<string, Revision | null>>({});
  const [literature, setLiterature] = useState<Literature[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>([]);
  const [selectedLiterature, setSelectedLiterature] = useState<string[]>([]);
  useEffect(() => {
    void api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(e instanceof Error ? e.message : t('errorLoad')));
  }, [t]);
  useEffect(() => {
    void api
      .listModelProfiles()
      .then(setProfiles)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!projectId) {
      setExperiments([]);
      return;
    }
    void api
      .listProjectExperiments(projectId)
      .then(setExperiments)
      .catch((e) => setError(e instanceof Error ? e.message : t('errorLoad')));
  }, [projectId, t]);
  function toggle(id: string) {
    setSelectedIds((items) => toggleBoundedSelection(items, id));
  }
  async function compare() {
    if (selectedIds.length < 2 || !projectId) return;
    setBusy(true);
    setError('');
    try {
      const value = await api.compareExperiments({
        project_id: projectId,
        experiment_ids: selectedIds
      });
      setResult(value);
      const revisionEntries = await Promise.all(
        selectedIds.map(async (id) => {
          const items = await api.listRevisions(id);
          return [id, items[0] ?? null] as const;
        })
      );
      setRevisions(Object.fromEntries(revisionEntries));
      if (projectId) {
        const [lit, ev] = await Promise.all([
          api.listLiterature(projectId),
          api.listEvidence(projectId)
        ]);
        setLiterature(lit);
        setEvidence(ev.filter((item) => item.status === 'active'));
      }
      const compatible = value.measurements.filter((item) => item.compatible);
      const loaded = await Promise.all(
        compatible.map(async (item) => [item.id, await api.listMeasurementPoints(item.id)] as const)
      );
      setPoints(Object.fromEntries(loaded));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errorCompare'));
    } finally {
      setBusy(false);
    }
  }
  async function analyse() {
    if (!result || selectedIds.length < 2) return;
    setBusy(true);
    setError('');
    try {
      const selections = selectedIds.map((id) => ({
        experiment_id: id,
        revision_number: revisions[id]?.revision_number ?? 1
      }));
      const measurements = result.measurements
        .filter((item) => item.compatible)
        .map((item) => item.id);
      const run = await api.createAnalysisRun(projectId, {
        experiment_selections: selections,
        measurement_ids: measurements,
        literature_ids: selectedLiterature,
        evidence_ids: selectedEvidence,
        model_profile_key: profileKey,
        prompt_version: 1
      });
      router.push(`/dashboard/analysis/${run.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('errorAnalysis'));
    } finally {
      setBusy(false);
    }
  }
  if (error && !projects.length) return <PageState error={error} />;
  return (
    <div className='flex flex-1 flex-col gap-6 px-4 pt-4 pb-8 md:px-6'>
      <PageHeader title={t('title')} description={t('description')} />
      <Card>
        <CardHeader>
          <SectionHeader title={t('selectionStep')} description={t('selectionHint')} />
        </CardHeader>
        <CardContent className='grid gap-4'>
          <select
            className='h-8 rounded-lg border bg-background px-2 text-sm'
            value={projectId}
            onChange={(e) => {
              setProjectId(e.target.value);
              setSelectedIds([]);
              setResult(null);
              setSelectedLiterature([]);
              setSelectedEvidence([]);
            }}
          >
            <option value=''>{t('chooseProject')}</option>
            {projects.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} · {item.title}
              </option>
            ))}
          </select>
          <div className='overflow-hidden rounded-lg border'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className='w-10'>{t('select')}</TableHead>
                  <TableHead>{t('experiment')}</TableHead>
                  <TableHead>{t('revision')}</TableHead>
                  <TableHead>{t('status')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {experiments.map((item) => (
                  <TableRow
                    key={item.id}
                    data-state={selectedIds.includes(item.id) ? 'selected' : undefined}
                  >
                    <TableCell>
                      <input
                        type='checkbox'
                        aria-label={item.code}
                        checked={selectedIds.includes(item.id)}
                        onChange={() => toggle(item.id)}
                      />
                    </TableCell>
                    <TableCell className='min-w-64 whitespace-normal'>
                      <div className='font-medium'>{item.title}</div>
                      <div className='font-mono text-xs text-muted-foreground'>{item.code}</div>
                    </TableCell>
                    <TableCell className='text-xs text-muted-foreground'>
                      {common('revisionTitle', { number: item.template_version })}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={item.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className='flex flex-wrap items-center justify-between gap-3'>
            <p className='text-sm text-muted-foreground'>
              {t('selectedCount', { count: selectedIds.length })} · {t('maxSelected')}
            </p>
            <Button onClick={compare} disabled={busy || selectedIds.length < 2}>
              {busy ? t('comparing') : t('compare', { count: selectedIds.length })}
            </Button>
          </div>
          {selectedIds.length > 0 && selectedIds.length < 2 ? (
            <p className='text-sm text-muted-foreground'>{t('selectAtLeastTwo')}</p>
          ) : null}
        </CardContent>
      </Card>
      {error ? (
        <p className='rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive'>{error}</p>
      ) : null}
      {result ? (
        <div className='grid gap-6'>
          <Card>
            <CardHeader>
              <SectionHeader
                title={t('analysisStep')}
                description={t('analysisConfigurationHint')}
              />
            </CardHeader>
            <CardContent className='grid gap-4'>
              <p className='text-sm text-muted-foreground'>{t('directSupportHint')}</p>
              <div className='grid gap-2 md:grid-cols-2'>
                <div>
                  <p className='mb-2 text-sm font-medium'>{t('revisions')}</p>
                  {selectedIds.map((id) => (
                    <p key={id} className='text-xs text-muted-foreground'>
                      {experiments.find((item) => item.id === id)?.code}:{' '}
                      {revisions[id]
                        ? common('revisionTitle', { number: revisions[id]?.revision_number })
                        : common('unknown')}
                    </p>
                  ))}
                </div>
                <div className='grid gap-2'>
                  <label className='text-sm font-medium' htmlFor='analysis-profile'>
                    {t('analysisProfile')}
                  </label>
                  <select
                    id='analysis-profile'
                    className='h-8 rounded-lg border bg-background px-2 text-sm'
                    value={profileKey}
                    onChange={(event) => setProfileKey(event.target.value)}
                  >
                    {profiles.map((profile) => (
                      <option key={profile.key} value={profile.key} disabled={!profile.available}>
                        {profile.label} · {profile.structured_output_mode}
                        {profile.available ? '' : ` (${profile.capability_reason})`}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className='grid gap-2 border-t pt-4 md:grid-cols-2'>
                <div>
                  <p className='mb-1 text-sm font-medium'>{t('literature')}</p>
                  <p className='mb-2 text-xs text-muted-foreground'>{t('optionalContext')}</p>
                  {literature.map((item) => (
                    <label key={item.id} className='flex items-center gap-2 text-xs'>
                      <input
                        type='checkbox'
                        checked={selectedLiterature.includes(item.id)}
                        onChange={() =>
                          setSelectedLiterature((current) =>
                            current.includes(item.id)
                              ? current.filter((id) => id !== item.id)
                              : [...current, item.id]
                          )
                        }
                      />
                      {item.title}
                    </label>
                  ))}
                </div>
                <div>
                  <p className='mb-1 text-sm font-medium'>{t('curatedEvidence')}</p>
                  <p className='mb-2 text-xs text-muted-foreground'>{t('optionalContext')}</p>
                  {evidence.map((item) => (
                    <label key={item.id} className='flex items-center gap-2 text-xs'>
                      <input
                        type='checkbox'
                        checked={selectedEvidence.includes(item.id)}
                        onChange={() =>
                          setSelectedEvidence((current) =>
                            current.includes(item.id)
                              ? current.filter((id) => id !== item.id)
                              : [...current, item.id]
                          )
                        }
                      />
                      {item.claim_text}
                    </label>
                  ))}
                </div>
              </div>
              <Button
                onClick={analyse}
                disabled={
                  busy || !profiles.some((item) => item.key === profileKey && item.available)
                }
              >
                {busy ? t('runningAnalysis') : t('runAnalysis')}
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <SectionHeader title={t('differencesStep')} description={t('differencesHint')} />
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('property')}</TableHead>
                    {result.experiments.map((item) => (
                      <TableHead key={item.id}>{item.code}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.structured_differences
                    .filter((row) => row.differs)
                    .map((row) => (
                      <TableRow key={row.path}>
                        <TableCell className='font-medium'>{row.label}</TableCell>
                        {result.experiments.map((item) => (
                          <TableCell key={item.id}>
                            {formatStructuredValue(row.values[item.id])}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
              {result.structured_differences.every((row) => !row.differs) ? (
                <p className='text-sm text-muted-foreground'>{t('noDifferences')}</p>
              ) : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <SectionHeader title={t('measurementOverlays')} description={t('overlaysHint')} />
            </CardHeader>
            <CardContent className='grid gap-6'>
              {result.measurements.length === 0 ? (
                <p className='text-sm text-muted-foreground'>{t('noMeasurements')}</p>
              ) : (
                <>
                  {result.measurements.map((item) => (
                    <div key={item.id} className='grid gap-2'>
                      <div className='flex flex-wrap justify-between gap-2 text-sm'>
                        <span className='font-medium'>
                          {item.name} · {item.experiment_id}
                        </span>
                        <span className={item.compatible ? 'text-primary' : 'text-destructive'}>
                          {item.compatible ? t('compatible') : item.incompatibility_reason}
                        </span>
                      </div>
                      <MetricStrip
                        className='sm:grid-cols-2 lg:grid-cols-5'
                        items={[
                          {
                            label: t('xRange'),
                            value: `${formatStructuredValue(item.summary_json.x_min)}–${formatStructuredValue(item.summary_json.x_max)} ${item.x_unit}`
                          },
                          {
                            label: t('yRange'),
                            value: `${formatStructuredValue(item.summary_json.y_min)}–${formatStructuredValue(item.summary_json.y_max)} ${item.y_unit}`
                          },
                          {
                            label: t('mean'),
                            value: formatStructuredValue(item.summary_json.y_mean)
                          },
                          { label: t('rows'), value: item.row_count },
                          {
                            label: t('source'),
                            value: item.id.slice(0, 10),
                            detail: t('measurementId')
                          }
                        ]}
                      />
                      {item.compatible ? (
                        <ChartContainer
                          config={{ series: { label: item.y_label, color: 'var(--chart-2)' } }}
                          className='min-h-56 w-full'
                        >
                          <LineChart accessibilityLayer data={points[item.id] ?? []}>
                            <CartesianGrid />
                            <XAxis dataKey='x_value' unit={item.x_unit} />
                            <YAxis dataKey='y_value' unit={item.y_unit} />
                            <Tooltip />
                            <Line dataKey='y_value' stroke='var(--color-series)' dot={false} />
                          </LineChart>
                        </ChartContainer>
                      ) : null}
                      <TechnicalDetails title={t('measurementProvenance')}>
                        <MetadataList
                          items={[
                            { label: t('measurementId'), value: item.id, mono: true },
                            { label: t('experimentId'), value: item.experiment_id, mono: true },
                            {
                              label: t('schema'),
                              value: `${item.schema_key} · v${item.schema_version}`
                            },
                            { label: t('rowCount'), value: item.row_count }
                          ]}
                          columns={2}
                        />
                      </TechnicalDetails>
                    </div>
                  ))}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
