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
      }
    ]
  }
];
