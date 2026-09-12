# Frontend — WarrantyTrack Web App

Next.js (App Router) + TypeScript + Tailwind. This is the entire user-facing UI.

## Run it

Normally you don't run this on its own — `docker compose up` from the repo root
starts it together with the API and the database, with hot reload.

To run it standalone (needs Node 22+):

```bash
cd frontend
npm install
cp .env.example .env.local   # only needed for AWS values
npm run dev                  # http://localhost:3000
```

| Script | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Production build (CI runs this) |
| `npm run lint` | ESLint (CI runs this) |
| `npm run typecheck` | `tsc --noEmit` (CI runs this) |

## Folder guide — where to put things

```
frontend/src/
├── app/          → Next.js routes (pages). One folder per URL segment.
│                   e.g. app/dashboard/page.tsx, app/assets/page.tsx
├── components/   → Reusable, generic UI (Button, Card, Modal, StatusBadge).
│                   Nothing feature-specific here.
├── features/     → Feature-specific UI + logic, grouped by domain.
│                   e.g. features/assets/, features/warranty/, features/ocr/
│                   This is where most screen-building work happens.
├── hooks/        → Shared custom React hooks (useAuth, useDebounce).
├── lib/          → API client, helpers, config. Talks to the backend.
├── types/        → Shared TypeScript types/interfaces.
├── styles/       → Global CSS beyond app/globals.css.
└── public/       → Static assets (logo, images, favicon).
```

**Rule of thumb:** if a component is used by only one feature, put it in
`features/<that-feature>/`. If it's generic and reused everywhere, put it in
`components/`.

## Talking to the backend

Never call `fetch` from a component. Everything goes through
[`src/lib/api.ts`](src/lib/api.ts), so auth headers, the base URL and error
handling stay in one place:

```ts
import { api } from "@/lib/api";

const health = await api.health();
```

Add a method to the `api` object for each endpoint you build. The request and
response shapes are agreed in [docs/api.md](../docs/api.md) — build against
those with mock data rather than waiting for the endpoint to exist.

Shared types live in [`src/types/index.ts`](src/types/index.ts) and must stay
in sync with the backend's Pydantic schemas. Change both in the same PR.

## Mapping to Figma / Jira

Each screen maps to a Figma frame ID (D01–D09) and a Jira task. Keep that ID in
the folder or component name so design ↔ code ↔ ticket stay traceable:

| Screen | Figma | Suggested location |
|---|---|---|
| Landing Page | D01 | `app/page.tsx` |
| Login / Sign Up | D02 | `features/auth/` |
| Workspace Selection | D03 | `features/workspace/` |
| Dashboard | D04 | `features/dashboard/` |
| Assets List | D05 | `features/assets/` |
| Add Asset (Upload) | D06 | `features/ocr/` |
| OCR Review | D07 | `features/ocr/` |
| Asset Detail | D08 | `features/assets/` |
| Notifications | D09 | `features/notifications/` |

> `app/page.tsx` is currently a placeholder that checks the backend connection.
> Whoever builds D01 replaces it.

## Conventions

- Components: `PascalCase.tsx`. Hooks: `useCamelCase.ts`.
- Import with the `@/` alias (`@/lib/api`), not long relative paths.
- Never call the backend directly from a component — go through `lib/api`.
- Never commit `.env.local`.
