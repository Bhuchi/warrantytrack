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

**Design file:** [WarrantyTrack on Figma](https://www.figma.com/design/Rf4eIrfmvy9QUwTp5hlKvL/WarrantyTrack)
— two pages: [`Desktop 1440x1024`](https://www.figma.com/design/Rf4eIrfmvy9QUwTp5hlKvL/WarrantyTrack?node-id=3312-2)
holds the D-numbered frames, [`Mobile 402x874`](https://www.figma.com/design/Rf4eIrfmvy9QUwTp5hlKvL/WarrantyTrack?node-id=3382-2)
holds the M-numbered ones.

**Build mobile first.** Mobile is the primary target, so pull the M frame,
build it with unprefixed Tailwind classes, then layer the D frame on with
`md:` overrides. Never write `max-md:`.

Each screen maps to a Figma frame ID and a Jira task. Keep that ID in the
folder or component name so design ↔ code ↔ ticket stay traceable:

| Screen | Figma | Location | Status |
|---|---|---|---|
| Landing Page | D01 / M01 | `app/(marketing)/page.tsx` | done |
| Login / Sign Up | D02 / M02 | `features/auth/` | done |
| Workspace Selection | D03 / M03 | `features/workspace/` | done |
| Dashboard | D04 / M04 | `features/dashboard/` | — |
| Assets List | D05 / M05 | `features/assets/` | — |
| Add Asset (Upload) | D06 / M06 | `features/ocr/` | — |
| OCR Review | D07 / M07 | `features/ocr/` | — |
| Asset Detail | D08 / M08 | `features/assets/` | — |
| Notifications | D09 / M09 | `features/notifications/` | — |
| Navigation Panel | M10 | `components/` | — |

> Several screens have two frames on the Mobile page — they are **states of the
> same screen** (e.g. M03 at `3382:71` has Organization selected, `3418:320`
> has Personal). Check both before building.

Marketing pages live in the `(marketing)` route group (header + footer chrome);
auth pages live in `(auth)` (full-bleed split screen). Parenthesised folders
group files without adding a URL segment.

## Conventions

- Components: `PascalCase.tsx`. Hooks: `useCamelCase.ts`.
- Import with the `@/` alias (`@/lib/api`), not long relative paths.
- Never call the backend directly from a component — go through `lib/api`.
- Never commit `.env.local`.
