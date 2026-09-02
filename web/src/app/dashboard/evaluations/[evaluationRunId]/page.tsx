import { EvaluationDetail } from '@/features/workspace/components/evaluation-detail';

export default async function EvaluationDetailPage({
  params
}: {
  params: Promise<{ evaluationRunId: string }>;
}) {
  const { evaluationRunId } = await params;
  return <EvaluationDetail evaluationRunId={evaluationRunId} />;
}
