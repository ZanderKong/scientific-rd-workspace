import {
  Box,
  Database,
  FlaskConical,
  FolderKanban,
  Gauge,
  Microscope,
  PackageSearch,
  Workflow
} from 'lucide-react';

export const navGroups = [
  {
    label: 'workspace',
    items: [
      { title: 'overview', url: '/dashboard/overview', icon: Gauge },
      { title: 'projects', url: '/dashboard/projects', icon: FolderKanban }
    ]
  },
  {
    label: 'research',
    items: [
      { title: 'experiments', url: '/dashboard/experiments', icon: FlaskConical },
      { title: 'samples', url: '/dashboard/samples', icon: PackageSearch },
      { title: 'processes', url: '/dashboard/processes', icon: Workflow },
      { title: 'data', url: '/dashboard/data', icon: Database }
    ]
  },
  {
    label: 'library',
    items: [
      { title: 'materials', url: '/dashboard/materials', icon: Box },
      { title: 'equipment', url: '/dashboard/equipment', icon: Microscope }
    ]
  }
] as const;
