import Providers from '@/components/layout/providers';
import { Toaster } from '@/components/ui/sonner';
import { fontVariables } from '@/components/themes/font.config';
import { DEFAULT_THEME, THEMES } from '@/components/themes/theme.config';
import ThemeProvider from '@/components/themes/theme-provider';
import { cn } from '@/lib/utils';
import type { Metadata, Viewport } from 'next';
import { cookies } from 'next/headers';
import NextTopLoader from 'nextjs-toploader';
import { NuqsAdapter } from 'nuqs/adapters/next/app';
import { getLocale, getMessages, getTranslations } from 'next-intl/server';
import { NextIntlClientProvider } from 'next-intl';
import { parseLocale } from '@/i18n/config';
import '../styles/globals.css';
import '@blocknote/shadcn/style.css';

const META_THEME_COLORS = {
  light: '#ffffff',
  dark: '#09090b'
};

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('Metadata');
  const title = t('title');
  const description = t('description');
  return {
    ...(process.env.NEXT_PUBLIC_APP_URL
      ? { metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL) }
      : {}),
    title: { default: title, template: `%s | ${title}` },
    description,
    openGraph: {
      title,
      description,
      siteName: title,
      type: 'website',
      images: [{ url: '/shadcn-dashboard.png', width: 3200, height: 1600, alt: t('imageAlt') }]
    },
    twitter: { card: 'summary_large_image', title, description, images: ['/shadcn-dashboard.png'] }
  };
}

export const viewport: Viewport = {
  themeColor: META_THEME_COLORS.light
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const activeThemeValue = cookieStore.get('active_theme')?.value;
  const isValidTheme = THEMES.some((t) => t.value === activeThemeValue);
  const themeToApply = isValidTheme ? activeThemeValue! : DEFAULT_THEME;
  const locale = parseLocale(await getLocale());
  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning data-theme={themeToApply}>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                // Set meta theme color
                if (localStorage.theme === 'dark' || ((!('theme' in localStorage) || localStorage.theme === 'system') && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', '${META_THEME_COLORS.dark}')
                }
              } catch (_) {}
            `
          }}
        />
      </head>
      <body
        className={cn(
          'bg-background overflow-x-hidden overscroll-none font-sans antialiased',
          fontVariables
        )}
      >
        <NextTopLoader color='var(--primary)' showSpinner={false} />
        <NuqsAdapter>
          <ThemeProvider
            attribute='class'
            defaultTheme='system'
            enableSystem
            disableTransitionOnChange
            enableColorScheme
          >
            <NextIntlClientProvider locale={locale} messages={messages}>
              <Providers activeThemeValue={themeToApply}>
                <Toaster />
                {children}
              </Providers>
            </NextIntlClientProvider>
          </ThemeProvider>
        </NuqsAdapter>
      </body>
    </html>
  );
}
