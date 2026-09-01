import { ExperimentList } from '@/features/workspace/components/experiment-table';
import { ButtonLink, PageHeader } from '@/features/workspace/components/shared';

export default function ExperimentsPage() {
  return (
    <div className='flex flex-1 flex-col px-4 pt-4 pb-8 md:px-6'>
      <PageHeader
        title='Experiments'
        description='Browse every experiment across your research projects.'
        action={
          <ButtonLink href='/dashboard/projects' variant='outline'>
            Choose a project
          </ButtonLink>
        }
      />
      <ExperimentList />
    </div>
  );
}
