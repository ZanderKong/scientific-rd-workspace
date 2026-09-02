import { AnalysisDetail } from '@/features/workspace/components/analysis-detail';

export default async function AnalysisDetailPage({
  params
}: {
  params: Promise<{ analysisRunId: string }>;
}) {
  const { analysisRunId } = await params;
  return <AnalysisDetail analysisRunId={analysisRunId} />;
}
