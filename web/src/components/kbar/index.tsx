'use client';
import { navGroups } from '@/config/nav-config';
import { KBarAnimator, KBarPortal, KBarPositioner, KBarProvider, KBarSearch } from 'kbar';
import { Kbd } from '@/components/ui/kbd';
import { useRouter } from 'next/navigation';
import { useCallback, useMemo } from 'react';
import RenderResults from './render-result';
import useThemeSwitching from './use-theme-switching';
import { useFilteredNavGroups } from '@/hooks/use-nav';
import { useTranslations } from 'next-intl';

const navLabelKeys = {
  Workspace: 'workspace',
  Research: 'research',
  Knowledge: 'knowledge',
  'AI & Evaluation': 'aiEvaluation',
  Overview: 'overview',
  Projects: 'projects',
  Experiments: 'experiments',
  Compare: 'compare',
  Literature: 'literature',
  Analysis: 'analysis',
  Evaluations: 'evaluations'
} as const;

export default function KBar({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const filteredGroups = useFilteredNavGroups(navGroups);
  const t = useTranslations('Navigation');
  const common = useTranslations('Common');
  const label = useCallback(
    (value: string) => {
      const key = navLabelKeys[value as keyof typeof navLabelKeys];
      return key ? t(key) : value;
    },
    [t]
  );

  // These action are for the navigation
  const actions = useMemo(() => {
    // Define navigateTo inside the useMemo callback to avoid dependency array issues
    const navigateTo = (url: string) => {
      router.push(url);
    };

    const allItems = filteredGroups.flatMap((group) => group.items);

    return allItems.flatMap((navItem) => {
      // Only include base action if the navItem has a real URL and is not just a container
      const baseAction =
        navItem.url !== '#'
          ? {
              id: `${navItem.title.toLowerCase()}Action`,
              name: label(navItem.title),
              shortcut: navItem.shortcut,
              keywords: navItem.title.toLowerCase(),
              section: t('workspace'),
              subtitle: `${common('open')}: ${label(navItem.title)}`,
              perform: () => navigateTo(navItem.url)
            }
          : null;

      // Map child items into actions
      const childActions =
        navItem.items?.map((childItem) => ({
          id: `${childItem.title.toLowerCase()}Action`,
          name: label(childItem.title),
          shortcut: childItem.shortcut,
          keywords: childItem.title.toLowerCase(),
          section: label(navItem.title),
          subtitle: `${common('open')}: ${label(childItem.title)}`,
          perform: () => navigateTo(childItem.url)
        })) ?? [];

      // Return only valid actions (ignoring null base actions for containers)
      return baseAction ? [baseAction, ...childActions] : childActions;
    });
  }, [common, filteredGroups, label, router, t]);

  return (
    <KBarProvider actions={actions}>
      <KBarComponent>{children}</KBarComponent>
    </KBarProvider>
  );
}
const KBarComponent = ({ children }: { children: React.ReactNode }) => {
  useThemeSwitching();
  const common = useTranslations('Common');

  return (
    <>
      <KBarPortal>
        <KBarPositioner className='bg-black/10 supports-backdrop-filter:backdrop-blur-xs fixed inset-0 z-99999 flex items-start! justify-center p-4! pt-[14vh]!'>
          <KBarAnimator className='bg-popover text-popover-foreground ring-foreground/10 relative mx-auto w-full max-w-[600px] overflow-hidden rounded-xl shadow-lg ring-1'>
            <div className='bg-popover sticky top-0 z-10 border-b'>
              <KBarSearch className='placeholder:text-muted-foreground w-full border-none bg-transparent px-4 py-3.5 text-sm outline-hidden focus:ring-0 focus:outline-hidden' />
            </div>
            <div className='h-[400px]'>
              <RenderResults />
            </div>
            <div className='text-muted-foreground flex items-center gap-3 border-t px-3 py-2 text-xs'>
              <span className='flex items-center gap-1'>
                <Kbd>↑</Kbd>
                <Kbd>↓</Kbd> {common('open')}
              </span>
              <span className='flex items-center gap-1'>
                <Kbd>↵</Kbd> {common('open')}
              </span>
              <span className='flex items-center gap-1'>
                <Kbd>esc</Kbd> {common('close')}
              </span>
            </div>
          </KBarAnimator>
        </KBarPositioner>
      </KBarPortal>
      {children}
    </>
  );
};
