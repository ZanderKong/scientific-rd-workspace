'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';
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
  SidebarRail
} from '@/components/ui/sidebar';
import { navGroups } from '@/config/nav-config';
import { ProjectSwitcher } from '@/features/workspace/project-scope/project-switcher';

export default function AppSidebar() {
  const t = useTranslations('Navigation');
  const pathname = usePathname();
  return (
    <Sidebar collapsible='icon'>
      <SidebarHeader>
        <ProjectSwitcher />
      </SidebarHeader>
      <SidebarContent className='overflow-x-hidden'>
        {navGroups.map((group) => (
          <SidebarGroup key={group.label} className='py-1'>
            <SidebarGroupLabel className='group-data-[collapsible=icon]:pointer-events-none'>
              {t(group.label)}
            </SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.url || pathname.startsWith(`${item.url}/`);
                return (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton
                      isActive={active}
                      tooltip={t(item.title)}
                      render={<Link href={item.url} aria-label={t(item.title)} />}
                    >
                      <Icon />
                      <span>{t(item.title)}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroup>
        ))}{' '}
      </SidebarContent>
      <SidebarFooter>
        <div className='px-3 py-2 text-[10px] text-sidebar-foreground/50 group-data-[collapsible=icon]:hidden'>
          {t('scopeHint')}
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
