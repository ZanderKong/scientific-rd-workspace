'use client';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail
} from '@/components/ui/sidebar';
import { navGroups } from '@/config/nav-config';
import { useFilteredNavGroups } from '@/hooks/use-nav';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icons } from '@/components/icons';
import { useTranslations } from 'next-intl';

const groupLabels = {
  Workspace: 'workspace',
  Research: 'research',
  Knowledge: 'knowledge',
  'AI & Evaluation': 'aiEvaluation'
} as const;

const itemLabels = {
  Overview: 'overview',
  Projects: 'projects',
  Experiments: 'experiments',
  Compare: 'compare',
  Literature: 'literature',
  Analysis: 'analysis',
  Evaluations: 'evaluations'
} as const;

export default function AppSidebar() {
  const t = useTranslations('Navigation');
  const pathname = usePathname();
  const filteredGroups = useFilteredNavGroups(navGroups);

  return (
    <Sidebar collapsible='icon'>
      <SidebarHeader />
      <SidebarContent className='overflow-x-hidden'>
        {filteredGroups.map((group) => (
          <SidebarGroup key={group.label || 'ungrouped'} className='py-0'>
            {group.label && (
              <SidebarGroupLabel>
                {t(groupLabels[group.label as keyof typeof groupLabels] ?? 'workspace')}
              </SidebarGroupLabel>
            )}
            <SidebarMenu>
              {group.items.map((item) => {
                const Icon = item.icon ? Icons[item.icon] : Icons.logo;
                return item?.items && item?.items?.length > 0 ? (
                  <Collapsible
                    key={item.title}
                    defaultOpen={item.isActive}
                    render={<SidebarMenuItem />}
                  >
                    <CollapsibleTrigger
                      render={
                        <SidebarMenuButton
                          tooltip={t(
                            itemLabels[item.title as keyof typeof itemLabels] ?? 'workspace'
                          )}
                          isActive={pathname === item.url}
                          className='group/collapsible'
                        />
                      }
                    >
                      {item.icon && <Icon />}
                      <span>
                        {t(itemLabels[item.title as keyof typeof itemLabels] ?? 'workspace')}
                      </span>
                      <Icons.chevronRight className='ml-auto transition-transform duration-200 group-data-panel-open/collapsible:rotate-90' />
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <SidebarMenuSub>
                        {item.items?.map((subItem) => (
                          <SidebarMenuSubItem key={subItem.title}>
                            <SidebarMenuSubButton
                              render={
                                <Link
                                  href={subItem.url}
                                  aria-label={t(
                                    itemLabels[subItem.title as keyof typeof itemLabels] ??
                                      'workspace'
                                  )}
                                />
                              }
                              isActive={pathname === subItem.url}
                            >
                              <span>
                                {t(
                                  itemLabels[subItem.title as keyof typeof itemLabels] ??
                                    'workspace'
                                )}
                              </span>
                            </SidebarMenuSubButton>
                          </SidebarMenuSubItem>
                        ))}
                      </SidebarMenuSub>
                    </CollapsibleContent>
                  </Collapsible>
                ) : (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      render={
                        <Link
                          href={item.url}
                          aria-label={t(
                            itemLabels[item.title as keyof typeof itemLabels] ?? 'workspace'
                          )}
                        />
                      }
                      tooltip={t(itemLabels[item.title as keyof typeof itemLabels] ?? 'workspace')}
                      isActive={pathname === item.url}
                    >
                      <Icon />
                      <span>
                        {t(itemLabels[item.title as keyof typeof itemLabels] ?? 'workspace')}
                      </span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <SidebarMenuButton
                    size='lg'
                    className='data-popup-open:bg-sidebar-accent data-popup-open:text-sidebar-accent-foreground'
                  />
                }
              >
                <span className='truncate'>{t('account')}</span>
                <Icons.chevronsDown className='ml-auto size-4' />
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className='w-(--anchor-width) min-w-56 rounded-lg'
                side='bottom'
                align='end'
                sideOffset={4}
              >
                <DropdownMenuGroup>
                  <DropdownMenuLabel className='p-0 font-normal'>
                    <div className='text-muted-foreground px-1 py-1.5 text-sm'>
                      {t('signInHint')}
                    </div>
                  </DropdownMenuLabel>
                </DropdownMenuGroup>
                <DropdownMenuSeparator />
                <DropdownMenuGroup></DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
