import { DataWorkspace } from '@/features/workspace/domain-workspaces';

export default async function DataDetailPage({ params }: { params: Promise<{ dataId: string }> }) {
  const { dataId } = await params;
  return <DataWorkspace dataId={dataId} />;
}
