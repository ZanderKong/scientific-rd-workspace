'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';

export function Breadcrumbs() {
  const pathname = usePathname();
  const t = useTranslations('Navigation');
  const segments = pathname.split('/').filter(Boolean);
  const label = segments[segments.length - 1] ?? 'overview';
  const known: Record<string, string> = {
    overview: 'overview',
    projects: 'projects',
    experiments: 'experiments',
    samples: 'samples',
    processes: 'processes',
    data: 'data',
    materials: 'materials',
    equipment: 'equipment',
    settings: 'settings',
    changes: 'changes',
    views: 'views',
    claims: 'claims',
    new: 'new',
    edit: 'edit'
  };
  const key = known[label] ?? known[segments[segments.length - 2] ?? ''] ?? 'overview';
  return (
    <nav aria-label='Breadcrumb' className='text-sm text-muted-foreground'>
      <Link href='/dashboard/samples' className='hover:text-foreground'>
        {t('workspace')}
      </Link>
      <span className='mx-2'>/</span>
      <span className='text-foreground'>{t(key)}</span>
    </nav>
  );
}
