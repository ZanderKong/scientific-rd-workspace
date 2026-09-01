import { ExperimentDetail } from '@/features/workspace/components/experiment-detail';

export default async function ExperimentDetailPage({
  params
}: {
  params: Promise<{ experimentId: string }>;
}) {
  const { experimentId } = await params;
  return <ExperimentDetail experimentId={experimentId} />;
}
