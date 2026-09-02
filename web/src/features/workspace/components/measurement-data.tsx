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
import { useLocale, useTranslations } from 'next-intl';
import { parseLocale } from '@/i18n/config';
import { formatNumber } from './shared';
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
  const locale = parseLocale(useLocale());
  const t = useTranslations('Measurements');
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
      onMessageRef.current(error instanceof Error ? error.message : t('errorLoad'), true)
    );
  }, [loadMeasurements, t]);

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
      onMessage(t('previewReady'));
    } catch (error) {
      onMessage(error instanceof Error ? error.message : t('errorPreview'), true);
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
      onMessage(t('imported'));
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
      onMessage(error instanceof Error ? error.message : t('errorImport'), true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className='grid gap-6'>
      <Card>
        <CardHeader>
          <CardTitle>{t('import')}</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-4'>
          <p className='text-sm text-muted-foreground'>{t('uploadHint')}</p>
          <div className='grid gap-2'>
            <Label>{t('attachment')}</Label>
            <select
              className='h-8 rounded-lg border bg-background px-2 text-sm'
              value={attachmentId}
              onChange={(event) => setAttachmentId(event.target.value)}
            >
              <option value=''>{t('chooseAttachment')}</option>
              {attachments.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.original_filename}
                </option>
              ))}
            </select>
          </div>
          {preview?.available_sheets.length ? (
            <div className='grid gap-2'>
              <Label>{t('worksheet')}</Label>
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
            {busy ? t('preparing') : t('preview')}
          </Button>
          {preview ? (
            <div className='grid gap-4 rounded-lg border p-4'>
              <div className='text-sm text-muted-foreground'>
                {t('previewRows', { count: preview.row_count ?? 0 })} ·{' '}
                {t('previewColumns', { count: preview.column_count ?? 0 })} · {t('sha256')}{' '}
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
                  <Label>{t('measurementName')}</Label>
                  <Input
                    value={mapping.name}
                    onChange={(event) => setMapping({ ...mapping, name: event.target.value })}
                  />
                </div>
                <div className='grid gap-2'>
                  <Label>{t('measurementType')}</Label>
                  <select
                    className='h-8 rounded-lg border bg-background px-2 text-sm'
                    value={mapping.type}
                    onChange={(event) => setMapping({ ...mapping, type: event.target.value })}
                  >
                    <option value='spectral_response'>{t('spectralResponse')}</option>
                    <option value='time_series'>{t('timeSeries')}</option>
                    <option value='other_xy'>{t('otherXY')}</option>
                  </select>
                </div>
                <div className='grid gap-2'>
                  <Label>{t('xColumn')}</Label>
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
                  <Label>{t('yColumn')}</Label>
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
                  <Label>{t('xLabelUnit')}</Label>
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
                  <Label>{t('yLabelUnit')}</Label>
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
                {busy ? t('importing') : t('validateImport')}
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
      <div className='grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]'>
        <Card>
          <CardHeader>
            <CardTitle>{t('title')}</CardTitle>
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
                        .catch(() => onMessage(t('errorPoints'), true));
                    }}
                    className='block w-full px-4 py-3 text-left hover:bg-muted'
                  >
                    <div className='font-medium'>{item.name}</div>
                    <div className='text-xs text-muted-foreground'>
                      {t(item.measurement_type)} · {t('rowCount', { count: item.row_count })} ·{' '}
                      {item.x_unit} / {item.y_unit}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className='p-4 text-sm text-muted-foreground'>{t('noMeasurements')}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{selected ? selected.name : t('selectMeasurement')}</CardTitle>
          </CardHeader>
          <CardContent>
            {selected ? (
              <div className='grid gap-4'>
                <div className='grid grid-cols-2 gap-3 text-sm md:grid-cols-5'>
                  {Object.entries(selected.summary_json).map(([key, value]) => (
                    <div key={key} className='rounded-lg border p-2'>
                      <div className='text-xs text-muted-foreground'>{key}</div>
                      <div className='font-medium'>{formatNumber(Number(value), locale)}</div>
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
                  {t('provenance', {
                    importId: selected.import_id,
                    attachmentId: selected.source_attachment_id
                  })}
                  {' · '}
                  {t('sha256')} {selected.source_sha256}
                </p>
              </div>
            ) : (
              <p className='text-sm text-muted-foreground'>{t('chooseMeasurement')}</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
