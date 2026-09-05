import { BadgeCheck, Database, FlaskConical, GitBranch, PackageSearch, Wrench } from 'lucide-react';

export const navGroups = [
  {
    label: 'research',
    items: [
      { title: 'experiments', url: '/dashboard/experiments', icon: FlaskConical },
      { title: 'samples', url: '/dashboard/samples', icon: PackageSearch },
      { title: 'equipment', url: '/dashboard/equipment', icon: Wrench },
      { title: 'data', url: '/dashboard/data', icon: Database },
      { title: 'views', url: '/dashboard/views', icon: GitBranch },
      { title: 'claims', url: '/dashboard/claims', icon: BadgeCheck }
    ]
  }
] as const;
