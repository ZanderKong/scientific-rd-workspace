import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function ProjectDetailPage({
  params
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <WorkspaceApp view='project' projectId={projectId} />;
}
