import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function MaterialDetailPage({
  params
}: {
  params: Promise<{ materialId: string }>;
}) {
  const { materialId } = await params;
  return <WorkspaceApp view='detail' objectId={materialId} />;
}
