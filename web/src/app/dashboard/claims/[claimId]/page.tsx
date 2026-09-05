import { ClaimWorkspace } from '@/features/workspace/domain-workspaces';

export default async function ClaimDetailPage({
  params
}: {
  params: Promise<{ claimId: string }>;
}) {
  const { claimId } = await params;
  return <ClaimWorkspace claimId={claimId} />;
}
