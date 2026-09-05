import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function ResearchObjectDetailPage({
  params
}: {
  params: Promise<{ objectId: string }>;
}) {
  const { objectId } = await params;
  return <WorkspaceApp view='detail' kind='research_object' objectId={objectId} />;
}
