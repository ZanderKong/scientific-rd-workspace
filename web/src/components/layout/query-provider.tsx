'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import dynamic from 'next/dynamic';
import { getQueryClient } from '@/lib/query-client';
import type * as React from 'react';
import { useEffect, useState } from 'react';
import { DEVTOOLS_EVENT, readDevtoolsPreference } from '@/features/settings/preferences-storage';

const ReactQueryDevtools = dynamic(
  () => import('@tanstack/react-query-devtools').then((module) => module.ReactQueryDevtools),
  { ssr: false }
);

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    if (process.env.NODE_ENV !== 'development') return;
    const read = () => setEnabled(readDevtoolsPreference());
    read();
    window.addEventListener(DEVTOOLS_EVENT, read);
    return () => window.removeEventListener(DEVTOOLS_EVENT, read);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && enabled && <ReactQueryDevtools />}
    </QueryClientProvider>
  );
}
