import AppSidebar from '@/components/layout/app-sidebar';
import Header from '@/components/layout/header';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import { getTranslations } from 'next-intl/server';

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('Metadata');
  return {
    title: t('dashboardTitle'),
    description: t('dashboardDescription'),
    robots: {
      index: false,
      follow: false
    }
  };
}

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  // Persisting the sidebar state in the cookie.
  const cookieStore = await cookies();
  const defaultOpen = cookieStore.get('sidebar_state')?.value === 'true';
  const t = await getTranslations('Common');
  return (
    <SidebarProvider defaultOpen={defaultOpen}>
      <a
        href='#main-content'
        className='bg-background ring-ring sr-only rounded-md px-3 py-2 text-sm font-medium shadow focus:not-sr-only focus:absolute focus:top-2 focus:start-2 focus:z-50 focus:ring-2'
      >
        {t('skipToContent')}
      </a>
      <AppSidebar />
      <SidebarInset id='main-content' tabIndex={-1} className='scroll-mt-16'>
        <Header />
        {children}
      </SidebarInset>
    </SidebarProvider>
  );
}
