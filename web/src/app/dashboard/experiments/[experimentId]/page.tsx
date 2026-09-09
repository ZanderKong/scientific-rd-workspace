import Link from 'next/link';

export default async function ExperimentDetailPage({
  params
}: {
  params: Promise<{ experimentId: string }>;
}) {
  await params;
  return (
    <main className='mx-auto w-full max-w-[900px] px-6 py-16'>
      <p className='text-sm text-muted-foreground'>记录不存在</p>
      <h1 className='mt-2 text-2xl font-semibold'>实验入口已移除</h1>
      <p className='mt-3 text-sm text-muted-foreground'>
        组织和比较内容请使用分析。原实验记录不会在此创建新的数据。
      </p>
      <Link className='mt-6 inline-flex text-sm font-medium text-primary underline-offset-4 hover:underline' href='/dashboard/analysis'>
        前往分析
      </Link>
    </main>
  );
}
