import { ExperimentCreate } from '@/features/workspace/components/experiment-create';

export default async function NewExperimentPage({
  params
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ExperimentCreate projectId={projectId} />;
}
