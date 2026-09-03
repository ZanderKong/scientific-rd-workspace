import { SampleDetail } from '@/features/workspace/sample-record/sample-detail';
import { getLocale } from 'next-intl/server';

export default async function SampleDetailPage({
  params
}: {
  params: Promise<{ sampleId: string }>;
}) {
  const { sampleId } = await params;
  const locale = await getLocale();
  return <SampleDetail sampleId={sampleId} zh={locale === 'zh-CN'} />;
}
