import { SidebarTrigger } from '../ui/sidebar';
import { Breadcrumbs } from '../breadcrumbs';
import { ThemeModeToggle } from '../themes/theme-mode-toggle';
import { LocaleSwitcher } from './locale-switcher';

export default function Header() {
  return (
    <header className='bg-background/80 sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-3 border-b px-3 backdrop-blur-md md:px-5'>
      <div className='flex min-w-0 items-center gap-3'>
        <SidebarTrigger />
        <Breadcrumbs />
      </div>
      <div className='flex shrink-0 items-center gap-2'>
        <LocaleSwitcher />
        <ThemeModeToggle />
      </div>
    </header>
  );
}
