import { SampleBatchEditor } from '@/features/workspace/sample-record/sample-batch-editor';

export default async function SampleBatchPage({
  params,
  searchParams
}: {
  params: Promise<{ sampleId: string }>;
  searchParams: Promise<{ revision?: string }>;
}) {
  const { sampleId } = await params;
  const { revision } = await searchParams;
  const parsed = revision ? Number(revision) : undefined;
  return (
    <SampleBatchEditor
      sampleId={sampleId}
      revision={Number.isFinite(parsed) ? parsed : undefined}
    />
  );
}
