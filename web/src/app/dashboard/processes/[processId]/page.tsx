import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function ProcessDetailPage({
  params
}: {
  params: Promise<{ processId: string }>;
}) {
  const { processId } = await params;
  return <WorkspaceApp view='detail' objectId={processId} />;
}
