import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function SampleDetailPage({
  params
}: {
  params: Promise<{ sampleId: string }>;
}) {
  const { sampleId } = await params;
  return <WorkspaceApp view='detail' objectId={sampleId} />;
}
