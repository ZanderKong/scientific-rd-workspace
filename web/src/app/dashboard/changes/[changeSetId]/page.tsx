import { ChangeSetWorkspace } from '@/features/workspace/domain-workspaces';

export default async function ChangeSetDetailPage({
  params
}: {
  params: Promise<{ changeSetId: string }>;
}) {
  const { changeSetId } = await params;
  return <ChangeSetWorkspace changeSetId={changeSetId} />;
}
