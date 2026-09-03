'use client';

import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
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
import { api } from '@/lib/api-client';
import type { ResearchObject } from '@/lib/domain';
import { navGroups } from '@/config/nav-config';

function ProjectSwitcher() {
  const locale = useLocale();
  const t = useTranslations('Navigation');
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [projects, setProjects] = useState<ResearchObject[]>([]);
  const [selected, setSelected] = useState('');
  useEffect(() => {
    api
      .listObjects({ kind: 'project', limit: 100 })
      .then(setProjects)
      .catch(() => setProjects([]));
  }, []);
  useEffect(() => {
    const fromUrl =
      searchParams.get('project') ?? pathname.match(/^\/dashboard\/projects\/([^/]+)/)?.[1];
    const saved = window.localStorage.getItem('scientific_workspace_project');
    const next = fromUrl ?? saved ?? projects[0]?.id ?? '';
    if (next) setSelected(next);
    if (!fromUrl && !saved && projects[0])
      window.localStorage.setItem('scientific_workspace_project', projects[0].id);
  }, [pathname, searchParams, projects]);
  function changeProject(id: string) {
    setSelected(id);
    window.localStorage.setItem('scientific_workspace_project', id);
    if (pathname.match(/^\/dashboard\/projects\/[^/]+$/)) router.push(`/dashboard/projects/${id}`);
    else {
      const params = new URLSearchParams(searchParams.toString());
      params.set('project', id);
      router.push(`${pathname}?${params.toString()}`);
    }
  }
  return (
    <div className='px-2 py-2 group-data-[collapsible=icon]:hidden'>
      <label className='mb-1 block px-2 text-[10px] font-medium uppercase tracking-widest text-sidebar-foreground/50'>
        {t('projectScope')}
      </label>
      <select
        value={selected}
        onChange={(event) => changeProject(event.target.value)}
        className='h-9 w-full rounded-md border border-sidebar-border bg-sidebar-accent px-2 text-xs text-sidebar-accent-foreground outline-none focus:ring-2 focus:ring-ring'
        aria-label={t('projectScope')}
      >
        {projects.length === 0 && <option value=''>{t('noProjects')}</option>}
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            {project.code} · {project.title}
          </option>
        ))}
      </select>
      <p className='mt-1 px-2 text-[10px] text-sidebar-foreground/50'>
        {locale === 'zh-CN' ? '当前视图作用域' : 'Current vault scope'}
      </p>
    </div>
  );
}

export default function AppSidebar() {
  const t = useTranslations('Navigation');
  const pathname = usePathname();
  return (
    <Sidebar collapsible='icon'>
      <SidebarHeader>
        <div className='flex items-center gap-2 px-2 py-2'>
          <div className='flex size-8 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground'>
            R
          </div>
          <div className='min-w-0 group-data-[collapsible=icon]:hidden'>
            <p className='truncate text-sm font-semibold'>Research Objects</p>
            <p className='truncate text-[10px] text-sidebar-foreground/60'>Scientific workspace</p>
          </div>
        </div>
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
