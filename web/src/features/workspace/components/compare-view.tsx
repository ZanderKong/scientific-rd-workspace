'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { PageHeader, PageState, StatusBadge } from './shared';

export function CompareView() {
  const router = useRouter();
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
      .catch((e) => setError(e instanceof Error ? e.message : 'Unable to load projects.'));
  }, []);
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
      .catch((e) => setError(e instanceof Error ? e.message : 'Unable to load experiments.'));
  }, [projectId]);
  function toggle(id: string) {
    setSelectedIds((items) =>
      items.includes(id)
        ? items.filter((item) => item !== id)
        : items.length < 5
          ? [...items, id]
          : items
    );
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
      setError(e instanceof Error ? e.message : 'Unable to compare experiments.');
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
      setError(e instanceof Error ? e.message : 'Unable to run scientific analysis.');
    } finally {
      setBusy(false);
    }
  }
  if (error && !projects.length) return <PageState error={error} />;
  return (
    <div className='flex flex-1 flex-col gap-6 px-4 pt-4 pb-8 md:px-6'>
      <PageHeader
        title='Compare experiments'
        description='Compare structured properties and compatible measurement overlays within one project.'
      />
      <Card>
        <CardHeader>
          <CardTitle>Choose experiments</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-4'>
          <select
            className='h-8 rounded-lg border bg-background px-2 text-sm'
            value={projectId}
            onChange={(e) => {
              setProjectId(e.target.value);
              setSelectedIds([]);
              setResult(null);
            }}
          >
            <option value=''>Choose a project</option>
            {projects.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} · {item.title}
              </option>
            ))}
          </select>
          <div className='grid gap-2 md:grid-cols-2'>
            {experiments.map((item) => (
              <label
                key={item.id}
                className='flex items-center gap-3 rounded-lg border p-3 text-sm'
              >
                <input
                  type='checkbox'
                  checked={selectedIds.includes(item.id)}
                  onChange={() => toggle(item.id)}
                />
                <span className='flex-1'>
                  <span className='font-medium'>{item.title}</span>
                  <span className='block text-xs text-muted-foreground'>
                    {item.code} · template v{item.template_version}
                  </span>
                </span>
                <StatusBadge status={item.status} />
              </label>
            ))}
          </div>
          <Button onClick={compare} disabled={busy || selectedIds.length < 2}>
            {busy ? 'Comparing…' : `Compare (${selectedIds.length})`}
          </Button>
          {selectedIds.length > 0 && selectedIds.length < 2 ? (
            <p className='text-sm text-muted-foreground'>Select at least two experiments.</p>
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
              <CardTitle>Scientific analysis configuration</CardTitle>
            </CardHeader>
            <CardContent className='grid gap-4'>
              <p className='text-sm text-muted-foreground'>
                Frozen revisions and compatible Measurements are sent to the server for validation.
                Curated Evidence is optional when direct structured support is sufficient.
              </p>
              <div className='grid gap-2 md:grid-cols-2'>
                <div>
                  <p className='mb-2 text-sm font-medium'>Experiment revisions</p>
                  {selectedIds.map((id) => (
                    <p key={id} className='text-xs text-muted-foreground'>
                      {experiments.find((item) => item.id === id)?.code}: Revision{' '}
                      {revisions[id]?.revision_number ?? 'missing'}
                    </p>
                  ))}
                </div>
                <div className='grid gap-2'>
                  <label className='text-sm font-medium' htmlFor='analysis-profile'>
                    Model profile
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
              <div className='grid gap-2 md:grid-cols-2'>
                <div>
                  <p className='mb-1 text-sm font-medium'>Literature (optional)</p>
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
                  <p className='mb-1 text-sm font-medium'>Curated Evidence (0–25, optional)</p>
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
                {busy ? 'Running analysis…' : 'Analyse selected experiments'}
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Structured property differences</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Property</TableHead>
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
                          <TableCell key={item.id}>{String(row.values[item.id] ?? '—')}</TableCell>
                        ))}
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
              {result.structured_differences.every((row) => !row.differs) ? (
                <p className='text-sm text-muted-foreground'>No structured differences.</p>
              ) : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Measurement overlays</CardTitle>
            </CardHeader>
            <CardContent className='grid gap-6'>
              {result.measurements.length === 0 ? (
                <p className='text-sm text-muted-foreground'>No measurements selected.</p>
              ) : (
                <>
                  {result.measurements.map((item) => (
                    <div key={item.id} className='grid gap-2'>
                      <div className='flex flex-wrap justify-between gap-2 text-sm'>
                        <span className='font-medium'>
                          {item.name} · {item.experiment_id}
                        </span>
                        <span className={item.compatible ? 'text-primary' : 'text-destructive'}>
                          {item.compatible ? 'Compatible' : item.incompatibility_reason}
                        </span>
                      </div>
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
