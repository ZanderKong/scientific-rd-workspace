import { ExperimentList } from '@/features/workspace/components/experiment-table';
import { ButtonLink, PageHeader } from '@/features/workspace/components/shared';
import { getTranslations } from 'next-intl/server';

export default async function ExperimentsPage() {
  const t = await getTranslations('Experiments');
  return (
    <div className='flex flex-1 flex-col px-4 pt-4 pb-8 md:px-6'>
      <PageHeader
        title={t('title')}
        description={t('description')}
        action={
          <ButtonLink href='/dashboard/projects' variant='outline'>
            {t('chooseProject')}
          </ButtonLink>
        }
      />
      <ExperimentList />
    </div>
  );
}
