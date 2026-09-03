import { ExperimentWorkspace } from '@/features/workspace/domain-workspaces';

export default async function ExperimentDetailPage({
  params
}: {
  params: Promise<{ experimentId: string }>;
}) {
  const { experimentId } = await params;
  return <ExperimentWorkspace experimentId={experimentId} />;
}
