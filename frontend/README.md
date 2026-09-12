# Frontend — WarrantyTrack Web App

Next.js (React) + TypeScript. This is the entire user-facing UI.

## Run locally

```bash
cd frontend
npm install
cp .env.example .env.local   # fill in values
npm run dev                  # http://localhost:3000
```

Other scripts: `npm run build`, `npm run lint`, `npm run test`.

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
├── styles/       → Global CSS / Tailwind config.
└── public/       → Static assets (logo, images, favicon).
```

**Rule of thumb:** if a component is used by only one feature, put it in
`features/<that-feature>/`. If it's generic and reused everywhere, put it in
`components/`.

## Mapping to Figma / Jira

**Design file:** [WarrantyTrack on Figma](https://www.figma.com/design/Rf4eIrfmvy9QUwTp5hlKvL/WarrantyTrack?node-id=3312-2)
— the `WarrantyTrack Desktop 1440x1024` page holds the D-numbered frames below.

Each screen maps to a Figma frame ID (D01–D09, N03) and a Jira task. Keep that
ID in the folder or component name so design ↔ code ↔ ticket stay traceable:

| Screen | Figma | Suggested location |
|---|---|---|
| Landing Page | D01 | `app/(marketing)/page.tsx` |
| Login / Sign Up | D02 | `features/auth/` |
| Workspace Selection | D03 | `features/workspace/` |
| Dashboard | D04 | `features/dashboard/` |
| Assets List | D05 | `features/assets/` |
| Add Asset (Upload) | D06 | `features/ocr/` |
| OCR Review | D07 | `features/ocr/` |
| Asset Detail | D08 | `features/assets/` |
| Notifications | D09 | `features/notifications/` |

## Conventions

- Components: `PascalCase.tsx`. Hooks: `useCamelCase.ts`.
- Never call the backend directly from a component — go through `lib/api`.
- Never commit `.env.local`.
