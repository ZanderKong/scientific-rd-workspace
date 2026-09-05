import { ViewWorkspace } from '@/features/workspace/domain-workspaces';

export default async function ViewDetailPage({ params }: { params: Promise<{ viewId: string }> }) {
  const { viewId } = await params;
  return <ViewWorkspace viewId={viewId} />;
}
