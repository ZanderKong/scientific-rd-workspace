import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function DataDetailPage({ params }: { params: Promise<{ dataId: string }> }) {
  const { dataId } = await params;
  return <WorkspaceApp view='detail' objectId={dataId} />;
}
