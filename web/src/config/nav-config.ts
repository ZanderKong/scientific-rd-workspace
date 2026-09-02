import { NavGroup } from '@/types';

export const navGroups: NavGroup[] = [
  {
    label: 'Scientific R&D',
    items: [
      {
        title: 'Overview',
        url: '/dashboard/overview',
        icon: 'dashboard',
        isActive: false,
        items: []
      },
      {
        title: 'Projects',
        url: '/dashboard/projects',
        icon: 'workspace',
        isActive: false,
        items: []
      },
      {
        title: 'Experiments',
        url: '/dashboard/experiments',
        icon: 'flask',
        isActive: false,
        items: []
      },
      {
        title: 'Compare',
        url: '/dashboard/compare',
        icon: 'trendingUp',
        isActive: false,
        items: []
      },
      {
        title: 'Literature',
        url: '/dashboard/literature',
        icon: 'post',
        isActive: false,
        items: []
      },
      {
        title: 'Analysis',
        url: '/dashboard/analysis',
        icon: 'sparkles',
        isActive: false,
        items: []
      },
      {
        title: 'Evaluations',
        url: '/dashboard/evaluations',
        icon: 'trendingUp',
        isActive: false,
        items: []
      }
    ]
  }
];
