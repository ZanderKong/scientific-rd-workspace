# ============================================
# Stage 1: Install dependencies
# ============================================

ARG NODE_VERSION=22-slim

FROM node:${NODE_VERSION} AS dependencies

WORKDIR /app

# Copy package-related files to leverage Docker cache
COPY package.json package-lock.json ./

# Install dependencies with frozen lockfile for reproducible builds
RUN npm ci --ignore-scripts

# ============================================
# Stage 2: Build the Next.js application
# ============================================

FROM node:${NODE_VERSION} AS builder

WORKDIR /app

COPY --from=dependencies /app/node_modules ./node_modules
COPY . .

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

ENV BUILD_STANDALONE=true
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ARG NEXT_PUBLIC_APP_URL
ARG NEXT_PUBLIC_APP_VERSION=0.2.0
ARG NEXT_PUBLIC_GIT_SHA
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL
ENV NEXT_PUBLIC_APP_VERSION=$NEXT_PUBLIC_APP_VERSION
ENV NEXT_PUBLIC_GIT_SHA=$NEXT_PUBLIC_GIT_SHA

RUN npm run build

# ============================================
# Stage 3: Production runner
# ============================================

FROM node:${NODE_VERSION} AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
ENV NEXT_TELEMETRY_DISABLED=1

# Copy public assets
COPY --from=builder --chown=node:node /app/public ./public

# Create .next dir with correct permissions for prerender cache
RUN mkdir .next && chown node:node .next

# Copy standalone output and static files
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

# Run as non-root user
USER node

EXPOSE 3000

CMD ["node", "server.js"]
