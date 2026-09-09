import { redirect } from 'next/navigation';

export default async function NewExperimentPage({
  params
}: {
  params: Promise<{ projectId: string }>;
}) {
  await params;
  redirect('/dashboard/analysis');
}
