'use client';

import Link from 'next/link';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import type { ExperimentStatus, ProjectStatus } from '@/lib/domain';
import type { AppLocale } from '@/i18n/config';

export const STATUS_TRANSLATION_KEYS = {
  active: 'active',
  paused: 'paused',
  completed: 'completed',
  archived: 'archived',
  draft: 'draft',
  planned: 'planned',
  running: 'running',
  cancelled: 'cancelled',
  failed: 'failed',
  pending: 'pending',
  completed_with_errors: 'completedWithErrors',
  preview_ready: 'previewReady',
  withdrawn: 'withdrawn',
  accepted: 'accepted',
  rejected: 'rejected',
  needs_evidence: 'needsEvidence',
  supported: 'supported',
  partially_supported: 'partiallySupported',
  insufficient_evidence: 'insufficientEvidence',
  contradicted: 'contradicted',
  bad_case: 'badCase',
  reference_case: 'referenceCase',
  pending_review: 'reviewPending'
} as const;

export type StatusTranslationKey =
  (typeof STATUS_TRANSLATION_KEYS)[keyof typeof STATUS_TRANSLATION_KEYS];

export function statusTranslationKey(status: string): StatusTranslationKey | undefined {
  return STATUS_TRANSLATION_KEYS[status as keyof typeof STATUS_TRANSLATION_KEYS];
}

export function formatDate(value: string, locale: AppLocale | string = 'zh-CN') {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value)
  );
}

export function formatNumber(value: number, locale: AppLocale | string = 'zh-CN') {
  return new Intl.NumberFormat(locale).format(value);
}

export function formatBytes(value: number, locale: AppLocale | string = 'zh-CN') {
  if (value < 1024) return `${formatNumber(value, locale)} B`;
  if (value < 1024 * 1024) return `${formatNumber(Number((value / 1024).toFixed(1)), locale)} KB`;
  return `${formatNumber(Number((value / (1024 * 1024)).toFixed(1)), locale)} MB`;
}

export function PageState({
  loading,
  error,
  empty,
  action
}: {
  loading?: boolean;
  error?: string;
  empty?: string;
  action?: React.ReactNode;
}) {
  const t = useTranslations('Common');
  if (loading)
    return (
      <div className='flex min-h-48 items-center justify-center text-muted-foreground'>
        <Loader2 className='mr-2 size-4 animate-spin' />
        {t('loading')}
      </div>
    );
  if (error)
    return (
      <Card>
        <CardContent className='flex items-center gap-3 py-8 text-destructive'>
          <AlertCircle className='size-5' />
          <span>{error}</span>
        </CardContent>
      </Card>
    );
  if (empty)
    return (
      <Card>
        <CardContent className='flex flex-col items-center justify-center gap-3 py-12 text-center'>
          <p className='text-muted-foreground'>{empty}</p>
          {action}
        </CardContent>
      </Card>
    );
  return null;
}

export function StatusBadge({ status }: { status: ProjectStatus | ExperimentStatus | string }) {
  const t = useTranslations('Status');
  const tone =
    status === 'completed'
      ? 'secondary'
      : status === 'cancelled' || status === 'archived'
        ? 'destructive'
        : status === 'running'
          ? 'default'
          : 'outline';
  const key = statusTranslationKey(status);
  return <Badge variant={tone}>{key ? t(key) : status.replaceAll('_', ' ')}</Badge>;
}

export function PageHeader({
  title,
  description,
  action
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className='mb-6 flex flex-wrap items-start justify-between gap-4'>
      <div>
        <h1 className='text-2xl font-semibold tracking-tight'>{title}</h1>
        <p className='mt-1 text-sm text-muted-foreground'>{description}</p>
      </div>
      {action}
    </div>
  );
}

export function BackLink({ href, children }: { href: string; children?: React.ReactNode }) {
  const t = useTranslations('Common');
  return (
    <Link className={buttonVariants({ variant: 'ghost', size: 'sm' })} href={href}>
      ← {children ?? t('back')}
    </Link>
  );
}

export function ButtonLink({
  href,
  children,
  variant = 'default',
  size = 'default'
}: {
  href: string;
  children: React.ReactNode;
  variant?: 'default' | 'outline' | 'secondary' | 'ghost' | 'destructive' | 'link';
  size?: 'default' | 'xs' | 'sm' | 'lg';
}) {
  return (
    <Link className={buttonVariants({ variant, size })} href={href}>
      {children}
    </Link>
  );
}
