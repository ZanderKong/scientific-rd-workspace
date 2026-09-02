'use client';

import Link from 'next/link';
import { ArrowUpRight, CheckCircle2, CircleDot, Info, Link2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type {
  ProjectStatus,
  ExperimentStatus,
  EvidenceGateStatus,
  EvaluationCaseType,
  JsonObject
} from '@/lib/domain';
import {
  formatStructuredValue,
  scoreEntries,
  technicalLabel,
  traceabilityNodes,
  type TraceabilityNode
} from '../presentation';
import { StatusBadge } from './shared';

export function SectionHeader({
  eyebrow,
  title,
  description,
  action
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className='flex flex-wrap items-start justify-between gap-3 border-b pb-3'>
      <div className='min-w-0'>
        {eyebrow ? (
          <p className='text-[0.68rem] font-semibold tracking-[0.16em] text-primary uppercase'>
            {eyebrow}
          </p>
        ) : null}
        <h2 className='mt-1 text-lg font-semibold tracking-tight'>{title}</h2>
        {description ? (
          <p className='mt-1 max-w-3xl text-sm text-muted-foreground'>{description}</p>
        ) : null}
      </div>
      {action ? <div className='shrink-0'>{action}</div> : null}
    </div>
  );
}

export function MetricStrip({
  items,
  className
}: {
  items: Array<{
    label: string;
    value: React.ReactNode;
    detail?: string;
    tone?: 'default' | 'primary' | 'warning';
  }>;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-2 lg:grid-cols-4',
        className
      )}
    >
      {items.map((item) => (
        <div
          key={item.label}
          className={cn(
            'min-w-0 bg-card px-4 py-3',
            item.tone === 'primary' && 'bg-primary/5',
            item.tone === 'warning' && 'bg-amber-500/5'
          )}
        >
          <p className='truncate text-[0.68rem] font-semibold tracking-[0.12em] text-muted-foreground uppercase'>
            {item.label}
          </p>
          <p className='mt-1 truncate text-xl font-semibold tabular-nums'>{item.value}</p>
          {item.detail ? (
            <p className='mt-1 truncate text-xs text-muted-foreground'>{item.detail}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function MetadataList({
  items,
  columns = 2
}: {
  items: Array<{ label: string; value: React.ReactNode; mono?: boolean }>;
  columns?: 1 | 2 | 3;
}) {
  return (
    <dl
      className={cn(
        'grid gap-x-6 gap-y-3',
        columns === 1
          ? 'grid-cols-1'
          : columns === 2
            ? 'sm:grid-cols-2'
            : 'sm:grid-cols-2 xl:grid-cols-3'
      )}
    >
      {items.map((item) => (
        <div key={item.label} className='min-w-0'>
          <dt className='text-xs font-medium text-muted-foreground'>{item.label}</dt>
          <dd className={cn('mt-1 break-words text-sm', item.mono && 'font-mono text-xs')}>
            {item.value ?? '—'}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function TechnicalDetails({
  title,
  children
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <details className='rounded-lg border bg-muted/20 p-3'>
      <summary className='cursor-pointer text-sm font-medium'>{title}</summary>
      <div className='mt-3 min-w-0'>{children}</div>
    </details>
  );
}

export function EntityIdentity({
  code,
  title,
  status,
  meta,
  description
}: {
  code?: string;
  title: string;
  status?: ProjectStatus | ExperimentStatus | string;
  meta?: React.ReactNode;
  description?: string | null;
}) {
  return (
    <div className='min-w-0'>
      <div className='flex flex-wrap items-center gap-2'>
        {code ? (
          <span className='font-mono text-xs font-semibold tracking-wide text-primary'>{code}</span>
        ) : null}
        {status ? <StatusBadge status={status} /> : null}
      </div>
      <h1 className='mt-2 break-words text-2xl font-semibold tracking-tight'>{title}</h1>
      {description ? (
        <p className='mt-2 max-w-3xl text-sm leading-6 text-muted-foreground'>{description}</p>
      ) : null}
      {meta ? (
        <div className='mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground'>
          {meta}
        </div>
      ) : null}
    </div>
  );
}

export function CaseTypeBadge({ caseType }: { caseType: EvaluationCaseType | string }) {
  const t = useTranslations('Status');
  return (
    <Badge variant={caseType === 'bad_case' ? 'destructive' : 'secondary'}>
      {caseType === 'bad_case' ? t('badCase') : t('referenceCase')}
    </Badge>
  );
}

export function EvidenceGateSummary({
  status,
  rationale,
  confidence,
  confidenceRationale
}: {
  status: EvidenceGateStatus | string;
  rationale: React.ReactNode;
  confidence?: string;
  confidenceRationale?: string;
}) {
  const t = useTranslations('Analysis');
  return (
    <div className='grid gap-3 sm:grid-cols-2'>
      <div className='rounded-xl border border-primary/30 bg-primary/5 p-4'>
        <div className='flex items-center justify-between gap-2'>
          <h3 className='font-medium'>{t('gate')}</h3>
          <StatusBadge status={status} />
        </div>
        <div className='mt-2 text-sm leading-6 text-muted-foreground'>{rationale || '—'}</div>
      </div>
      <div className='rounded-xl border bg-muted/20 p-4'>
        <div className='flex items-center justify-between gap-2'>
          <h3 className='font-medium'>{t('confidence')}</h3>
          {confidence ? <Badge variant='outline'>{confidence}</Badge> : null}
        </div>
        <p className='mt-2 text-sm leading-6 text-muted-foreground'>{confidenceRationale || '—'}</p>
      </div>
    </div>
  );
}

export function ScoreSummary({
  scores,
  title
}: {
  scores: JsonObject | null | undefined;
  title: string;
}) {
  const entries = scoreEntries(scores);
  return (
    <div className='grid gap-3'>
      <h3 className='text-sm font-semibold'>{title}</h3>
      {entries.length ? (
        <div className='grid gap-2 sm:grid-cols-2 lg:grid-cols-3'>
          {entries.map((entry) => (
            <div key={entry.key} className='rounded-lg border bg-muted/20 px-3 py-2'>
              <div className='text-xs text-muted-foreground'>{entry.label}</div>
              <div className='mt-1 break-words text-sm font-semibold tabular-nums'>
                {formatStructuredValue(entry.value)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className='text-sm text-muted-foreground'>—</p>
      )}
    </div>
  );
}

export function ProvenanceSummary({
  title,
  items,
  note
}: {
  title: string;
  items: Array<{ label: string; value: React.ReactNode; href?: string }>;
  note?: React.ReactNode;
}) {
  return (
    <Card className='border-primary/20'>
      <CardHeader className='pb-3'>
        <CardTitle className='flex items-center gap-2 text-base'>
          <Link2 className='size-4 text-primary' />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className='grid gap-3'>
        <MetadataList
          items={items.map((item) => ({
            label: item.label,
            value: item.href ? (
              <Link className='font-mono text-xs text-primary hover:underline' href={item.href}>
                {item.value}
                <ArrowUpRight className='ml-1 inline size-3' />
              </Link>
            ) : (
              item.value
            )
          }))}
          columns={1}
        />
        {note ? <p className='text-xs leading-5 text-muted-foreground'>{note}</p> : null}
      </CardContent>
    </Card>
  );
}

export function TraceabilityTimeline({
  title,
  nodes
}: {
  title: string;
  nodes: TraceabilityNode[];
}) {
  const items = traceabilityNodes(nodes);
  return (
    <Card>
      <CardHeader className='pb-3'>
        <CardTitle className='flex items-center gap-2 text-base'>
          <CircleDot className='size-4 text-primary' />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length ? (
          <ol className='grid gap-0'>
            {items.map((node, index) => (
              <li key={node.id} className='relative flex gap-3 pb-4 last:pb-0'>
                {index < items.length - 1 ? (
                  <span
                    className='absolute top-5 left-[0.45rem] h-full w-px bg-border'
                    aria-hidden='true'
                  />
                ) : null}
                <span
                  className='relative mt-1 flex size-2.5 shrink-0 rounded-full bg-primary ring-4 ring-primary/10'
                  aria-hidden='true'
                />
                <div className='min-w-0 flex-1'>
                  <div className='flex flex-wrap items-center gap-2 text-sm'>
                    <span className='text-[0.68rem] font-semibold tracking-[0.12em] text-muted-foreground uppercase'>
                      {technicalLabel(node.kind)}
                    </span>
                    {node.href ? (
                      <Link href={node.href} className='font-medium text-primary hover:underline'>
                        {node.label}
                        <ArrowUpRight className='ml-1 inline size-3' />
                      </Link>
                    ) : (
                      <span className='font-medium'>{node.label}</span>
                    )}
                  </div>
                  {node.detail ? (
                    <p className='mt-1 break-words text-xs leading-5 text-muted-foreground'>
                      {node.detail}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <div className='flex items-center gap-2 text-sm text-muted-foreground'>
            <Info className='size-4' />—
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function StateMarker({ done, label }: { done: boolean; label: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-xs',
        done ? 'text-primary' : 'text-muted-foreground'
      )}
    >
      <CheckCircle2 className='size-3.5' />
      {label}
    </span>
  );
}
