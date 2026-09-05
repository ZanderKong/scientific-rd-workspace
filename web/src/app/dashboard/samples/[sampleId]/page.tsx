import { SampleDetail } from '@/features/workspace/sample-record/sample-detail';

export default async function SampleDetailPage({
  params
}: {
  params: Promise<{ sampleId: string }>;
}) {
  const { sampleId } = await params;
  return <SampleDetail sampleId={sampleId} />;
}
