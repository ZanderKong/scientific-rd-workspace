import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function NewExperimentPage({
  params
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <WorkspaceApp view='new' kind='experiment' projectId={projectId} />;
}
