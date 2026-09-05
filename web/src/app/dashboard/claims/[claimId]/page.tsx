import { WorkspaceApp } from '@/features/workspace/components/workspace-app';

export default async function ClaimDetailPage({ params }: { params: Promise<{ claimId: string }> }) {
  const { claimId } = await params;
  return <WorkspaceApp view='detail' kind='claim' objectId={claimId} />;
}
