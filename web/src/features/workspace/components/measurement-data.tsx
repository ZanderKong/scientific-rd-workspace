'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { ChartContainer } from '@/components/ui/chart';
import { ApiError, api } from '@/lib/api-client';
import type {
  Attachment,
  Experiment,
  ImportPreview,
  Measurement,
  MeasurementPoint
} from '@/lib/domain';

export function MeasurementData({
  experiment,
  attachments,
  onMessage
}: {
  experiment: Experiment;
  attachments: Attachment[];
  onMessage: (message: string, error?: boolean) => void;
}) {
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [selected, setSelected] = useState<Measurement | null>(null);
  const [points, setPoints] = useState<MeasurementPoint[]>([]);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [attachmentId, setAttachmentId] = useState('');
  const [sheet, setSheet] = useState('');
  const [busy, setBusy] = useState(false);
  const [mapping, setMapping] = useState({
    name: '',
    type: 'other_xy',
    chart: 'line',
    x: '',
    y: '',
    xLabel: 'X',
    yLabel: 'Y',
    xUnit: '1',
    yUnit: '1'
  });
  const onMessageRef = useRef(onMessage);
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const loadMeasurements = useCallback(async () => {
    const rows = await api.listMeasurements(experiment.id);
    setMeasurements(rows);
  }, [experiment.id]);
  useEffect(() => {
    void loadMeasurements().catch((error) =>
      onMessageRef.current(
        error instanceof Error ? error.message : 'Unable to load measurements.',
        true
      )
    );
  }, [loadMeasurements]);

  async function startPreview() {
    if (!attachmentId) return;
    setBusy(true);
    try {
      const value = await api.previewMeasurementImport(
        experiment.id,
        attachmentId,
        sheet || undefined
      );
      setPreview(value);
      setMapping((current) => ({
        ...current,
        name: current.name || 'Measurement',
        x: value.headers[0] ?? '',
        y: value.headers[1] ?? '',
        chart: current.chart
      }));
      onMessage('Preview ready. Map one X and one Y column before committing.');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'Unable to preview import.', true);
    } finally {
      setBusy(false);
    }
  }
  async function commit() {
    if (!preview || !mapping.x || !mapping.y) return;
    setBusy(true);
    try {
      await api.commitMeasurementImport(preview.id, {
        measurement_name: mapping.name,
        measurement_type: mapping.type,
        default_chart_type: mapping.chart,
        sheet_name: preview.sheet_name,
        x: { column: mapping.x, label: mapping.xLabel, unit: mapping.xUnit },
        y: { column: mapping.y, label: mapping.yLabel, unit: mapping.yUnit }
      });
      setPreview(null);
      onMessage('Measurement imported.');
      await loadMeasurements();
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.details &&
        typeof error.details === 'object' &&
        'import_id' in error.details &&
        typeof error.details.import_id === 'string'
      ) {
        const failed = await api.getMeasurementImport(error.details.import_id).catch(() => null);
        if (failed) setPreview(failed);
      }
      onMessage(error instanceof Error ? error.message : 'Unable to commit import.', true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className='grid gap-6'>
      <Card>
        <CardHeader>
          <CardTitle>Import measurement</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-4'>
          <p className='text-sm text-muted-foreground'>
            Supported shape: UTF-8 comma-separated CSV or one visible worksheet in XLSX, with one
            numeric X/Y series.
          </p>
          <div className='grid gap-2'>
            <Label>Raw Attachment</Label>
            <select
              className='h-8 rounded-lg border bg-background px-2 text-sm'
              value={attachmentId}
              onChange={(event) => setAttachmentId(event.target.value)}
            >
              <option value=''>Choose an attachment</option>
              {attachments.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.original_filename}
                </option>
              ))}
            </select>
          </div>
          {preview?.available_sheets.length ? (
            <div className='grid gap-2'>
              <Label>Worksheet</Label>
              <select
                className='h-8 rounded-lg border bg-background px-2 text-sm'
                value={sheet || preview.sheet_name || ''}
                onChange={(event) => setSheet(event.target.value)}
              >
                {preview.available_sheets.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </div>
          ) : null}
          <Button onClick={startPreview} disabled={busy || !attachmentId}>
            {busy ? 'Preparing…' : 'Preview file'}
          </Button>
          {preview ? (
            <div className='grid gap-4 rounded-lg border p-4'>
              <div className='text-sm text-muted-foreground'>
                {preview.row_count} rows · {preview.column_count} columns · SHA-256{' '}
                {preview.source_sha256}
              </div>
              <div className='overflow-x-auto'>
                <Table>
                  <TableHeader>
                    <TableRow>
                      {preview.headers.map((header) => (
                        <TableHead key={header}>{header}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.preview_rows.map((row, index) => (
                      <TableRow key={index}>
                        {row.map((value, cell) => (
                          <TableCell key={cell}>{String(value ?? '')}</TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className='grid gap-3 md:grid-cols-2'>
                <div className='grid gap-2'>
                  <Label>Measurement name</Label>
                  <Input
                    value={mapping.name}
                    onChange={(event) => setMapping({ ...mapping, name: event.target.value })}
                  />
                </div>
                <div className='grid gap-2'>
                  <Label>Type</Label>
                  <select
                    className='h-8 rounded-lg border bg-background px-2 text-sm'
                    value={mapping.type}
                    onChange={(event) => setMapping({ ...mapping, type: event.target.value })}
                  >
                    <option value='spectral_response'>Spectral response</option>
                    <option value='time_series'>Time series</option>
                    <option value='other_xy'>Other X/Y</option>
                  </select>
                </div>
                <div className='grid gap-2'>
                  <Label>X column</Label>
                  <select
                    className='h-8 rounded-lg border bg-background px-2 text-sm'
                    value={mapping.x}
                    onChange={(event) => setMapping({ ...mapping, x: event.target.value })}
                  >
                    {preview.headers.map((header) => (
                      <option key={header}>{header}</option>
                    ))}
                  </select>
                </div>
                <div className='grid gap-2'>
                  <Label>Y column</Label>
                  <select
                    className='h-8 rounded-lg border bg-background px-2 text-sm'
                    value={mapping.y}
                    onChange={(event) => setMapping({ ...mapping, y: event.target.value })}
                  >
                    {preview.headers.map((header) => (
                      <option key={header}>{header}</option>
                    ))}
                  </select>
                </div>
                <div className='grid gap-2'>
                  <Label>X label / unit</Label>
                  <div className='flex gap-2'>
                    <Input
                      value={mapping.xLabel}
                      onChange={(event) => setMapping({ ...mapping, xLabel: event.target.value })}
                    />
                    <Input
                      value={mapping.xUnit}
                      onChange={(event) => setMapping({ ...mapping, xUnit: event.target.value })}
                    />
                  </div>
                </div>
                <div className='grid gap-2'>
                  <Label>Y label / unit</Label>
                  <div className='flex gap-2'>
                    <Input
                      value={mapping.yLabel}
                      onChange={(event) => setMapping({ ...mapping, yLabel: event.target.value })}
                    />
                    <Input
                      value={mapping.yUnit}
                      onChange={(event) => setMapping({ ...mapping, yUnit: event.target.value })}
                    />
                  </div>
                </div>
              </div>
              {preview.errors.length ? (
                <div className='rounded-md bg-destructive/10 p-3 text-sm text-destructive'>
                  {preview.errors.map((item, index) => (
                    <p key={index}>{item.message}</p>
                  ))}
                </div>
              ) : null}
              {preview.warnings.length ? (
                <div className='rounded-md bg-primary/10 p-3 text-sm'>
                  {preview.warnings.map((item, index) => (
                    <p key={index}>{item.message}</p>
                  ))}
                </div>
              ) : null}
              <Button
                onClick={commit}
                disabled={busy || mapping.x === mapping.y || !mapping.name.trim()}
              >
                {busy ? 'Importing…' : 'Validate and import'}
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
      <div className='grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]'>
        <Card>
          <CardHeader>
            <CardTitle>Measurements</CardTitle>
          </CardHeader>
          <CardContent className='p-0'>
            {measurements.length ? (
              <div className='divide-y'>
                {measurements.map((item) => (
                  <button
                    type='button'
                    key={item.id}
                    onClick={() => {
                      setSelected(item);
                      void api
                        .listMeasurementPoints(item.id)
                        .then(setPoints)
                        .catch(() => onMessage('Unable to load points.', true));
                    }}
                    className='block w-full px-4 py-3 text-left hover:bg-muted'
                  >
                    <div className='font-medium'>{item.name}</div>
                    <div className='text-xs text-muted-foreground'>
                      {item.measurement_type} · {item.row_count} rows · {item.x_unit} /{' '}
                      {item.y_unit}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className='p-4 text-sm text-muted-foreground'>No measurements yet.</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{selected ? selected.name : 'Select a measurement'}</CardTitle>
          </CardHeader>
          <CardContent>
            {selected ? (
              <div className='grid gap-4'>
                <div className='grid grid-cols-2 gap-3 text-sm md:grid-cols-5'>
                  {Object.entries(selected.summary_json).map(([key, value]) => (
                    <div key={key} className='rounded-lg border p-2'>
                      <div className='text-xs text-muted-foreground'>{key}</div>
                      <div className='font-medium'>{Number(value).toPrecision(5)}</div>
                    </div>
                  ))}
                </div>
                <ChartContainer
                  config={{ series: { label: selected.y_label, color: 'var(--chart-1)' } }}
                  className='min-h-72 w-full'
                >
                  <>
                    {selected.default_chart_type === 'scatter' ? (
                      <ScatterChart accessibilityLayer data={points}>
                        <CartesianGrid />
                        <XAxis dataKey='x_value' name={selected.x_label} unit={selected.x_unit} />
                        <YAxis dataKey='y_value' name={selected.y_label} unit={selected.y_unit} />
                        <Tooltip />
                        <Scatter dataKey='y_value' fill='var(--color-series)' />
                      </ScatterChart>
                    ) : (
                      <LineChart accessibilityLayer data={points}>
                        <CartesianGrid />
                        <XAxis dataKey='x_value' name={selected.x_label} unit={selected.x_unit} />
                        <YAxis dataKey='y_value' name={selected.y_label} unit={selected.y_unit} />
                        <Tooltip />
                        <Line
                          type='monotone'
                          dataKey='y_value'
                          stroke='var(--color-series)'
                          dot={false}
                        />
                      </LineChart>
                    )}
                  </>
                </ChartContainer>
                <p className='text-xs text-muted-foreground'>
                  Provenance: import {selected.import_id} · attachment{' '}
                  {selected.source_attachment_id} · SHA-256 {selected.source_sha256}
                </p>
              </div>
            ) : (
              <p className='text-sm text-muted-foreground'>
                Choose an imported measurement to inspect its immutable points and provenance.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
