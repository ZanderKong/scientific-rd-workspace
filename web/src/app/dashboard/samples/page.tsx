import { SampleList } from '@/features/workspace/sample-record/sample-list';
import { getLocale } from 'next-intl/server';

export default async function SamplesPage() {
  const locale = await getLocale();
  return <SampleList zh={locale === 'zh-CN'} />;
}
