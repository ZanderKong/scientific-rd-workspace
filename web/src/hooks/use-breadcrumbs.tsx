'use client';

import { usePathname } from 'next/navigation';
import { useMemo } from 'react';

type BreadcrumbItem = {
  title: string;
  link: string;
};

// This allows to add custom title as well
const routeMapping: Record<string, BreadcrumbItem[]> = {
  '/dashboard': [{ title: 'Overview', link: '/dashboard/overview' }],
  '/dashboard/overview': [{ title: 'Overview', link: '/dashboard/overview' }],
  '/dashboard/projects': [{ title: 'Projects', link: '/dashboard/projects' }],
  '/dashboard/experiments': [{ title: 'Experiments', link: '/dashboard/experiments' }]
};

export function useBreadcrumbs() {
  const pathname = usePathname();

  const breadcrumbs = useMemo(() => {
    // Check if we have a custom mapping for this exact path
    if (routeMapping[pathname]) {
      return routeMapping[pathname];
    }

    if (pathname.startsWith('/dashboard/projects/')) {
      return [
        { title: 'Projects', link: '/dashboard/projects' },
        { title: 'Project', link: pathname }
      ];
    }

    if (pathname.startsWith('/dashboard/experiments/')) {
      return [
        { title: 'Experiments', link: '/dashboard/experiments' },
        { title: 'Experiment', link: pathname }
      ];
    }

    // If no exact match, fall back to generating breadcrumbs from the path
    const segments = pathname.split('/').filter(Boolean);
    return segments.map((segment, index) => {
      const path = `/${segments.slice(0, index + 1).join('/')}`;
      return {
        title: segment.charAt(0).toUpperCase() + segment.slice(1),
        link: path
      };
    });
  }, [pathname]);

  return breadcrumbs;
}
