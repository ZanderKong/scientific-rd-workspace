import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function NewEquipmentPage() {
  return <WorkspaceApp view='list' kind='research_object' tag='设备' />;
}
