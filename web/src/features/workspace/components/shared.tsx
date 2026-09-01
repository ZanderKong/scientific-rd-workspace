'use client';

import Link from 'next/link';
import { AlertCircle, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import type { ExperimentStatus, ProjectStatus } from '@/lib/domain';

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
  if (loading)
    return (
      <div className='flex min-h-48 items-center justify-center text-muted-foreground'>
        <Loader2 className='mr-2 size-4 animate-spin' />
        Loading workspace…
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
  const tone =
    status === 'completed'
      ? 'secondary'
      : status === 'cancelled' || status === 'archived'
        ? 'destructive'
        : status === 'running'
          ? 'default'
          : 'outline';
  return <Badge variant={tone}>{status.replaceAll('_', ' ')}</Badge>;
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value)
  );
}

export function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
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

export function BackLink({
  href,
  children = 'Back'
}: {
  href: string;
  children?: React.ReactNode;
}) {
  return (
    <Link className={buttonVariants({ variant: 'ghost', size: 'sm' })} href={href}>
      ← {children}
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
