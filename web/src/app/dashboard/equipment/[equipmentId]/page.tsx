import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function EquipmentDetailPage({
  params
}: {
  params: Promise<{ equipmentId: string }>;
}) {
  const { equipmentId } = await params;
  return <WorkspaceApp view='detail' kind='research_object' objectId={equipmentId} />;
}
