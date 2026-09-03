import { FlaskConical, PackageSearch } from 'lucide-react';

export const navGroups = [
  {
    label: 'research',
    items: [
      { title: 'experiments', url: '/dashboard/experiments', icon: FlaskConical },
      { title: 'samples', url: '/dashboard/samples', icon: PackageSearch }
    ]
  }
] as const;
