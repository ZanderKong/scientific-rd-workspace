'use client';

import { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { QuickSettingsCard } from './quick-settings-card';

const DELAY = 200;

export function SettingsTrigger() {
  const t = useTranslations('Settings');
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const timer = useRef<number | null>(null);
  function cancelClose() {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = null;
  }
  function delayedClose() {
    cancelClose();
    timer.current = window.setTimeout(() => setOpen(false), DELAY);
  }
  function show() {
    cancelClose();
    setOpen(true);
  }
  return (
    <div
      className='fixed right-4 bottom-[max(1rem,env(safe-area-inset-bottom))] z-40'
      onMouseEnter={show}
      onMouseLeave={delayedClose}
    >
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          render={
            <Button
              variant='outline'
              size='icon'
              className='size-9 rounded-full bg-background/90 shadow-md'
              aria-label={t('trigger')}
              onFocus={show}
              onClick={() => router.push('/dashboard/settings')}
            />
          }
        >
          <Settings2 className='size-4' />
        </PopoverTrigger>
        <PopoverContent
          side='top'
          align='end'
          sideOffset={10}
          className='w-auto border-0 bg-transparent p-0 shadow-none'
          onMouseEnter={show}
          onMouseLeave={delayedClose}
          onFocusCapture={show}
        >
          <QuickSettingsCard onMouseEnter={show} onMouseLeave={delayedClose} />
        </PopoverContent>
      </Popover>
    </div>
  );
}
