# Deployment

The v0.2 web app can run on Vercel or anywhere Docker runs. `next.config.ts` uses standalone output when `BUILD_STANDALONE=true`, so production builds are suitable for self-hosting.

## Vercel (Recommended)

1. Connect the repository to Vercel
2. Add environment variables in the dashboard
3. Deploy

For other platforms, see the [Next.js deployment docs](https://nextjs.org/docs/app/getting-started/deploying).

## Environment Variables for Production

Ensure these are set in your deployment platform:

- All `NEXT_PUBLIC_*` variables for client-side access

## Docker

Two production-ready Dockerfiles are included: `Dockerfile` (Node.js) and `Dockerfile.bun` (Bun runtime image). Both install the canonical `package-lock.json` with `npm ci`. Set `NEXT_PUBLIC_API_URL` at build/runtime as required.

Build the image:

```bash
# Node.js
docker build \
  -t scientific-rd-workspace-web .

# OR Bun
docker build -f Dockerfile.bun \
  -t scientific-rd-workspace-web .
```

Run the container:

```bash
docker run -d -p 3000:3000 \
  --restart unless-stopped \
  --name scientific-rd-workspace-web \
  scientific-rd-workspace-web
```
