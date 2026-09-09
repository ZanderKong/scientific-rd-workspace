import { BadgeCheck, Database, GitBranch, LibraryBig, PackageSearch } from 'lucide-react';

export const navGroups = [
  {
    label: 'research',
    items: [
      { title: 'samples', url: '/dashboard/samples', icon: PackageSearch },
      { title: 'analysis', url: '/dashboard/analysis', icon: GitBranch },
      { title: 'data', url: '/dashboard/data', icon: Database },
      { title: 'claims', url: '/dashboard/claims', icon: BadgeCheck },
      { title: 'resources', url: '/dashboard/resources', icon: LibraryBig }
    ]
  }
] as const;
