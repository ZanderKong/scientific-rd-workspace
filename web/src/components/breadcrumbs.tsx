'use client';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from '@/components/ui/breadcrumb';
import { useBreadcrumbs } from '@/hooks/use-breadcrumbs';
import { Icons } from '@/components/icons';
import { Fragment } from 'react';
import { useTranslations } from 'next-intl';

const breadcrumbLabels: Record<
  string,
  'overview' | 'projects' | 'experiments' | 'compare' | 'literature' | 'analysis' | 'evaluations'
> = {
  overview: 'overview',
  projects: 'projects',
  experiments: 'experiments',
  compare: 'compare',
  literature: 'literature',
  analysis: 'analysis',
  evaluations: 'evaluations',
  project: 'projects',
  experiment: 'experiments'
};

export function Breadcrumbs() {
  const items = useBreadcrumbs();
  const t = useTranslations('Navigation');
  if (items.length === 0) return null;

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {items.map((item, index) => (
          <Fragment key={item.title}>
            {index !== items.length - 1 && (
              <BreadcrumbItem className='hidden md:block'>
                <BreadcrumbLink href={item.link}>
                  {t(breadcrumbLabels[item.title] ?? 'workspace')}
                </BreadcrumbLink>
              </BreadcrumbItem>
            )}
            {index < items.length - 1 && (
              <BreadcrumbSeparator className='hidden md:block'>
                <Icons.slash />
              </BreadcrumbSeparator>
            )}
            {index === items.length - 1 && (
              <BreadcrumbPage>{t(breadcrumbLabels[item.title] ?? 'workspace')}</BreadcrumbPage>
            )}
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
