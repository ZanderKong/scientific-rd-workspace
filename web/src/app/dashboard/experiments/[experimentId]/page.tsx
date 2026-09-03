import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function ExperimentDetailPage({
  params
}: {
  params: Promise<{ experimentId: string }>;
}) {
  const { experimentId } = await params;
  return <WorkspaceApp view='detail' objectId={experimentId} />;
}
