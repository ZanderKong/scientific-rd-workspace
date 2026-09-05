import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function ViewDetailPage({ params }: { params: Promise<{ viewId: string }> }) {
  const { viewId } = await params;
  return <WorkspaceApp view='detail' kind='view' objectId={viewId} />;
}
