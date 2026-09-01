'use client';

import { useEffect, useState } from 'react';
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
import type { CompareResult, Experiment, MeasurementPoint, Project } from '@/lib/domain';
import { PageHeader, PageState, StatusBadge } from './shared';

export function CompareView() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [projectId, setProjectId] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [points, setPoints] = useState<Record<string, MeasurementPoint[]>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    void api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(e instanceof Error ? e.message : 'Unable to load projects.'));
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
