import type { NextConfig } from 'next';
import createNextIntlPlugin from 'next-intl/plugin';
import packageJson from './package.json';

const nextConfig: NextConfig = {
  output: process.env.BUILD_STANDALONE === 'true' ? 'standalone' : undefined,
  devIndicators: false,
  env: {
    NEXT_PUBLIC_APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION ?? packageJson.version,
    NEXT_PUBLIC_GIT_SHA: process.env.NEXT_PUBLIC_GIT_SHA ?? 'unknown'
  },
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production'
  }
};

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');

export default withNextIntl(nextConfig);
