# Deployment

The Scientific R&D Workspace web app can run on Vercel or anywhere Docker runs. `next.config.ts` uses standalone output when `BUILD_STANDALONE=true`, so the Node image can be self-hosted.

## Vercel

1. Connect the repository to Vercel
2. Add environment variables in the dashboard
3. Deploy

For other platforms, see the [Next.js deployment docs](https://nextjs.org/docs/app/getting-started/deploying).

## Environment Variables

Ensure these are set in your deployment platform:

- `NEXT_PUBLIC_API_URL`: public API base, injected at build time
- `NEXT_PUBLIC_APP_URL`: optional metadata base URL
- `NEXT_PUBLIC_APP_VERSION`: optional displayed build version
- `NEXT_PUBLIC_GIT_SHA`: optional displayed build commit

## Docker

`Dockerfile` is the supported production image. It installs the canonical `package-lock.json` with `npm ci` and uses standalone output. Public Next.js variables must be present when building the image.

Build the image:

```bash
# Node.js
docker build \
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 \
  -t scientific-rd-workspace-web .
```

Run the container:

```bash
docker run -d -p 3000:3000 \
  --restart unless-stopped \
  --name scientific-rd-workspace-web \
  scientific-rd-workspace-web
```
