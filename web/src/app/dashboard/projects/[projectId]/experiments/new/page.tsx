import { ExperimentWorkspace } from '@/features/workspace/domain-workspaces';

export default async function NewExperimentPage({
  params
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ExperimentWorkspace projectId={projectId} create />;
}
