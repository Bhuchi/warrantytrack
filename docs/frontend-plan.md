# Frontend Plan — Jira tickets and timeline

Working plan for the **frontend half** of WarrantyTrack. Backend and AWS work is
owned by the rest of the team and is not scheduled here — it appears below only
where it blocks a frontend ticket.

| | |
|---|---|
| Owners | Chaiyapat "Earth" Anantarasuchart ([@erthcyp](https://github.com/erthcyp)) · Poonnawit "Bright" Wongprateepwilai ([@Aphelios514](https://github.com/Aphelios514)) |
| Board | `CLOUDAPPG5` (Kanban) |
| Window | 14 Oct 2026 → 17 Nov 2026 (final delivery) |
| Design | Figma — [Desktop](https://www.figma.com/design/Rf4eIrfmvy9QUwTp5hlKvL/WarrantyTrack?node-id=3312-2) · [Mobile](https://www.figma.com/design/Rf4eIrfmvy9QUwTp5hlKvL/WarrantyTrack?node-id=3382-2) |

## Who is scheduled here, and who is not

Only **Chaiyapat's** tickets carry dates. He owns those, so he can commit to
them.

**Poonnawit's tickets are assigned but deliberately carry no dates.** Guessing
someone else's schedule puts commitments on the board that they never agreed
to. He sets his own start and due date when he picks each one up.

Same in Jira: create Poonnawit's tickets with summary, description, epic and
assignee filled in, and leave start date and due date empty.

### How Poonnawit's four tickets were chosen

Poonnawit is new to React, and will be working with AI help against this repo.
So his tickets are the ones that are **self-contained and have no React state**:

| | Why it suits a first ticket |
|---|---|
| FE-03 states | Three tiny components, nothing depends on them yet |
| FE-13 Notifications | A list rendered with `.map()`, no interaction |
| FE-14 Settings | Toggles, copied from an existing pattern in the repo |
| FE-08 Asset Detail | Read-only, lays out data it is handed |

Each carries a **prompt to start with** — paste it into an AI session opened on
this repo. Writing the prompt in Thai is fine; the repo and this file are in
English so the AI has the context either way.

Anything needing `useState`, shared state across screens, or wiring to the API
stays with Chaiyapat. That is why Assets List (search and filters) and the
toasts are not on this list.

> **Load warning.** This leaves Chaiyapat with 13 of the 17 tickets, several of
> them overlapping in the first week of November. That is not realistic for one
> person alongside UX work. Before it bites, cut scope — in order: the Documents
> screen, the organization Settings variants (M12), and the desktop web push
> (N03). None of them are on the demo path.

## Before touching the Jira board

This file is a **plan**, not a mirror of the board. The board moves on its own —
other people add issues, rename them, change statuses, and the keys quoted here
may be wrong by the time you read it. **Read the board first, then reconcile.**

1. **List what actually exists.** `searchJiraIssuesUsingJql` with
   `project = CLOUDAPPG5 ORDER BY created ASC`. Do not assume any key in this
   file is still correct.
2. **Match by summary text, not by key.** The keys quoted below were
   reconciled against the board on 14 Oct 2026, but they can drift again. If
   an issue with the same summary already exists under a different key, edit
   it — do not create a duplicate. (An earlier draft quoted CLOUDAPPG5-13, -14
   and -115; those never existed, and early commits that cite them are not
   linked to any ticket.)
3. **Check the workflow before moving anything.** Status names vary per
   project. Read the transitions available on a real issue before calling
   `transitionJiraIssue`; do not guess that "Done" or "In Progress" exist.
4. **Check the issue types.** "Epic" is not guaranteed to be the name on a
   team-managed board. Read what types the project offers before creating.
5. **Show the diff before writing.** Tell Chaiyapat what you intend to create,
   edit and move, and wait. A bulk create against a board that already has
   tickets is hard to undo.
6. **Then** create what is genuinely missing, and update this file so it
   matches the board again.

## Making the Jira Timeline actually render

The Timeline view draws nothing for issues without dates. For the instructor to
see a real schedule:

1. A scheduled issue needs a **Start date** (`customfield_10015`) and a **Due
   date** (`duedate`) — both, not just due. Poonnawit's issues have neither on
   purpose; their bars appear once he schedules them.
2. Every issue must be **linked to an Epic**. Timeline draws one bar per epic
   and nests children inside it.
3. **Leave the Epic dates empty.** Jira rolls an epic's bar up from its
   children, so the bar grows on its own as people schedule their tickets —
   and nobody gets a date they did not agree to.
4. On a Kanban board, enable the Timeline view in Board settings if it is hidden.

## Epics

The board's epics are **by project phase**, set up by Bhuchi. We use them as
they are rather than adding a second, feature-based set — a ticket can only
have one parent epic, and two parallel structures would split the Timeline.
The `###` groupings below are for reading this file only; they are not epics.

| Epic | Key | Frontend tickets in it |
|---|---|---|
| Development: Front-end web | CLOUDAPPG5-59 | Everything except the two below |
| Testing | CLOUDAPPG5-61 | FE-15 |
| Deliverables | CLOUDAPPG5-63 | FE-17 |

Epics carry no dates — the bar comes from whatever children get scheduled.

Board facts, read 14 Oct 2026: issue types are Epic, Story, Task, Bug,
Subtask (tickets here are **Task**); statuses are `To Do`, `In Progress`,
`Done` for every type.

## Done already

| Key | Summary | Status |
|---|---|---|
| CLOUDAPPG5-81 | Landing page (D01 / M01) + Next.js scaffold | Done |
| CLOUDAPPG5-82 | Login / Sign Up screen (D02 / M02) | Done |
| CLOUDAPPG5-83 | Workspace Selection screen (D03 / M03) | Done |

> Merged to `main` in PR #1 on 16 Oct 2026. All three are UI-only: no screen
> talks to the API yet. Wiring is tracked separately below so the board does
> not overstate progress.

## On hold — needs a team decision

- **Scope of Poonnawit's existing tickets.** CLOUDAPPG5-88 (Asset Detail)
  includes an Edit button and Quick Actions; -89 (Notifications) includes
  filter tabs and Mark all as read. Both need React state, which FE-08 and
  FE-13 below deliberately leave out. Agree the narrower scope with the team
  or split those parts into separate tickets.

## Frontend tickets

Keys in each heading are the board keys as of 14 Oct 2026. Tickets
reused from the board keep their original (longer) summary there.

Build order is mobile frame first, then `md:` overrides for desktop.

### Design System & App Shell

**FE-01 · Build shared UI component library** · `CLOUDAPPG5-119`
- Assignee: Chaiyapat (@erthcyp) · Start 17 Oct · Due 21 Oct
- Extract `Button`, `StatusBadge`, `Card`, `Modal`, `Toast` into `components/`
  from the patterns already repeated across D01–D03.
- AC: each has a mobile and `md:` desktop variant; `StatusBadge` renders
  Active / Expiring Soon / Expired / No warranty; no raw hex outside
  `app/globals.css`.

**FE-02 · Build navigation panel and signed-in app shell (M10)** · `CLOUDAPPG5-120`
- Assignee: Chaiyapat (@erthcyp) · Start 17 Oct · Due 22 Oct
- Figma `3392:2` and `3455:536`. Drawer nav for mobile, sidebar for desktop
  (`3382:1309`). Includes sign-out, which mobile currently has nowhere.
- AC: route group for signed-in screens; nav highlights the current route;
  drawer traps focus and closes on Escape and on backdrop tap.

**FE-03 · Loading, empty and error state components** · `CLOUDAPPG5-121` — *start here*
- Assignee: Poonnawit (@Aphelios514) · Dates: Poonnawit to set
- Three small components, nothing else depends on them yet. The gentlest
  possible first ticket.
- AC: `Skeleton`, `EmptyState` and `ErrorState` in `components/`; each works at
  402px and 1440px; colours come from the tokens in `app/globals.css`, never
  raw hex; `EmptyState` and `ErrorState` take a message and an optional action.
- Prompt to start with:
  > Read `frontend/README.md` and `docs/frontend-plan.md` first. Then create
  > three components in `frontend/src/components/`: `Skeleton`, `EmptyState`
  > and `ErrorState`. Copy the styling conventions from the existing
  > `components/TextField.tsx` and `components/AppBar.tsx` — mobile-first
  > Tailwind, `md:` for desktop, colour tokens only. Run `npm run lint`,
  > `npm run typecheck` and `npm run build` before you finish.

### User Management System

**FE-04 · Wire auth screens to Cognito** · `CLOUDAPPG5-122`
- Assignee: Chaiyapat (@erthcyp) · Start 24 Oct · Due 31 Oct
- Blocked by: backend Cognito setup + `/auth` endpoints.
- AC: sign in, sign up and sign out work end to end; token supplied through
  `setAuthTokenProvider` in `lib/api`; unauthenticated users are redirected;
  form validation and server errors shown inline.

**FE-05 · Wire workspace selection to the API** · `CLOUDAPPG5-123`
- Assignee: Chaiyapat (@erthcyp) · Start 28 Oct · Due 31 Oct
- Blocked by: backend `/workspaces` endpoint.
- AC: real workspaces and counts replace the Figma placeholders; the chosen
  workspace persists and scopes every later request.

### Product / Asset Management

**FE-06 · Build Dashboard (D04 / M04)** · `CLOUDAPPG5-84`
- Assignee: Chaiyapat (@erthcyp) · Start 20 Oct · Due 26 Oct
- Figma `3382:141`, `3418:385`. Summary counts, warranty status breakdown.
- AC: shows active / expiring soon / expired / no-warranty totals; org view
  can group by department, location, category, vendor; mock data behind a
  single function so swapping to the API is one change.

**FE-07 · Build Assets List with search and filters (D05 / M05)** · `CLOUDAPPG5-85`
- Assignee: Chaiyapat (@erthcyp) · Start 3 Nov · Due 9 Nov
- Figma `3382:296`, `3418:524`, filters `3396:7503`.
- Kept with Chaiyapat because search and filtering need client state, which is
  the part of React that is hardest to get right while still learning it.
- AC: filter by warranty status; search by name and serial; empty state;
  list virtualises or paginates past 50 rows.

**FE-08 · Build Asset Detail (D08 / M08)** · `CLOUDAPPG5-88`
- Assignee: Poonnawit (@Aphelios514) · Dates: Poonnawit to set
- Figma `3382:676`, `3455:318`.
- Read-only screen — no forms, no state. Lays out data it is handed.
- AC: shows warranty dates and computed status, attached documents, and the
  box/storage photo and note from Add Asset step 3; mock data sits in one
  object at the top of the file so swapping to the API later is one change.
- Prompt to start with:
  > Read `frontend/README.md` and `docs/frontend-plan.md`. Build the Asset
  > Detail screen at `frontend/src/app/(app)/assets/[id]/page.tsx` from Figma
  > node `3382:676` on the Mobile page, then layer desktop on with `md:` from
  > node `3455:318`. Use the Figma MCP tools to read the design. Follow
  > `app/(app)/dashboard/page.tsx` for the page shape and
  > `features/workspace/WorkspaceCard.tsx` for card styling. Mock data only —
  > put it in one object at the top. Run lint, typecheck and build.

### Document and OCR Management

**The Add Asset flow**, agreed 14 Oct; the serial number was made required on
18 Oct, matching Bhuchi's CLOUDAPPG5-116 / -118. Three steps, each ending in
edit → confirm / cancel:

```
Add Asset
├─ 1. Receipt / invoice          REQUIRED — no skip, every workspace
│     OCR the receipt, or enter manually. Manual is offered up front
│     and automatically when OCR fails. This is the information that
│     identifies the asset, so the step must produce data either way.
│     Required in personal and organization workspaces alike — without
│     it there is no way to tell what the asset even is.
├─ 2. Serial number              REQUIRED, no skip
│     Scan it or type it. Needed when making a warranty claim.
└─ 3. Box / storage photo        OPTIONAL — skippable
      Photo of the box or where it is kept, plus a free-text note.
      Shown later on Asset Detail, for warranties that need the box.
```


**FE-09 · Add Asset step 1 — receipt (D06 / M06)** · `CLOUDAPPG5-86`
- Assignee: Chaiyapat (@erthcyp) · Start 27 Oct · Due 2 Nov
- Figma (3-step flow, mobile): choose method `3569:187`, OCR failed
  `3569:274`, review receipt `3569:361`. Older frames: `3382:447`, `3436:1771`,
  stepper `3396:7449`.
- **This step cannot be skipped.** It carries the information that identifies
  the asset, so there is no Skip control — only two ways in:
  1. **OCR** — upload or capture the receipt, Textract fills the fields, the
     user edits and confirms.
  2. **Enter manually** — available up front, and offered automatically when
     OCR fails or returns nothing usable.
- AC: no Skip control anywhere on this step, in **either** workspace type —
  personal and organization behave the same here; "Enter manually" is reachable
  without first attempting OCR; camera capture works on mobile; every OCR
  field is editable before confirm; required fields are validated before
  Confirm enables; cancel discards the whole wizard without saving.

**FE-10 · Add Asset step 2: serial number, required** · *not on the board yet*
- Assignee: Chaiyapat (@erthcyp) · Start 2 Nov · Due 5 Nov
- Figma (mobile): `3569:454`.
- Scan the serial with the camera, or type it. There is no way to skip.
- AC: no Skip control; Confirm stays disabled until a serial is entered; a
  low-confidence OCR result is flagged and editable; a hint says where to find
  the serial. Matches the backend validation in CLOUDAPPG5-118.

**FE-11 · Add Asset step 3: box / storage photo, optional** · *not on the board yet*
- Assignee: Chaiyapat (@erthcyp) · Start 5 Nov · Due 8 Nov
- Figma (mobile): `3569:568`.
- Photo of the box or where it is stored, plus a free-text note.
- AC: both fields optional; "Skip for now" still saves the asset; photo and
  note appear on Asset Detail.

**FE-12 · Build OCR Review screen (D07 / M07)** · `CLOUDAPPG5-87`
- Assignee: Chaiyapat (@erthcyp) · Start 3 Nov · Due 10 Nov
- Figma `3382:566`, `3455:225`. In the 3-step flow this is the review at the
  end of step 1 (`3569:361`); the serial number field moved to step 2.
- AC: extracted values shown beside the source image; low-confidence fields
  flagged; user can correct every field; confirm writes the verified values.

### Warranty Notification

**FE-13 · Build Notifications screen (D09 / M09)** · `CLOUDAPPG5-89`
- Assignee: Poonnawit (@Aphelios514) · Dates: Poonnawit to set
- Figma `3382:794`, `3455:421`.
- A list of rows. Read/unread is a visual difference only at this stage —
  nothing has to be saved anywhere yet.
- AC: list of expiry notifications; unread rows visually distinct; empty state
  reuses `EmptyState` from FE-03; mock data in one array at the top of the file.
- Out of scope, kept for later: the toast variants (`3488:171`, `3488:286`)
  need shared state across screens, so they are not part of this ticket.
- Prompt to start with:
  > Read `frontend/README.md` and `docs/frontend-plan.md`. Build the
  > Notifications screen at `frontend/src/app/(app)/notifications/page.tsx`
  > from Figma node `3382:794` on the Mobile page, then layer desktop on with
  > `md:` from `3455:421`. Use the Figma MCP tools to read the design. Follow
  > `features/auth/BrandPanel.tsx` for how a list is rendered with `.map()`
  > and a `key`. Mock data only, in one array at the top. No React state —
  > if you think you need `useState`, ask first. Run lint, typecheck and build.

**FE-14 · Build Settings — notifications (M11)** · `CLOUDAPPG5-124`
- Assignee: Poonnawit (@Aphelios514) · Dates: Poonnawit to set
- Figma `3464:171`. The organization variants (`3468:171`, `3494:171`) are a
  separate, later ticket — build the personal one first.
- AC: the toggle rows from the frame, laid out and styled; toggles flip
  visually; nothing is persisted yet.
- Prompt to start with:
  > Read `frontend/README.md` and `docs/frontend-plan.md`. Build the Settings
  > screen at `frontend/src/app/(app)/settings/page.tsx` from Figma node
  > `3464:171` on the Mobile page, then layer desktop on with `md:`. Use the
  > Figma MCP tools to read the design. For the toggles, copy the pattern in
  > `features/auth/SignInForm.tsx` where a checkbox is styled with
  > `appearance-none` and `peer-checked:`. Nothing needs to be saved yet.
  > Run lint, typecheck and build.

### Release & QA

**FE-15 · Responsive and accessibility QA pass** · `CLOUDAPPG5-125`
- Assignee: Chaiyapat (@erthcyp) · Start 11 Nov · Due 14 Nov
- AC: every screen checked at 402 px and 1440 px on a real device; no
  horizontal scroll; tap targets ≥ 44 px; labels on all inputs; keyboard
  navigation works; colour contrast checked against the brand blue.

**FE-16 · Frontend integration with deployed backend** · `CLOUDAPPG5-126`
- Assignee: Chaiyapat (@erthcyp) · Start 12 Nov · Due 16 Nov
- Blocked by: ECS deployment.
- AC: `NEXT_PUBLIC_API_URL` points at the ALB; every screen runs on real data;
  no mock data left in the bundle.

**FE-17 · Demo script and report screenshots** · `CLOUDAPPG5-127`
- Assignee: Chaiyapat (@erthcyp) · Start 14 Nov · Due 17 Nov
- AC: a scripted happy path for the demo; screenshots of each screen for the
  final report.

## Risks

| Risk | Why | Mitigation |
|---|---|---|
| OCR is the longest pole | Textract integration plus a three-step wizard plus a review screen — four tickets, two weeks | Build the wizard against mock OCR output first; do not wait for Textract |
| Backend blocks FE-04/05/16 | Auth, workspaces and deployment are owned by other teammates | Keep mock data behind one function per feature so screens are demoable regardless |
| Scope | 14 screens left in 5 weeks for two people | Drop first, in order: bulk import, organization settings (M12), desktop web push (N03) |

## Backend dependencies to raise with the team

These block frontend tickets and are worth agreeing dates for:

1. Cognito user pool + sign-in endpoints — needed by **4 Nov** for FE-04
2. `/workspaces` and `/memberships` — needed by **28 Oct** for FE-05
3. `/assets` CRUD — needed by **3 Nov** for FE-07
4. S3 presigned upload + Textract endpoint — needed by **3 Nov** for FE-09
5. ECS deployment reachable over the ALB — needed by **12 Nov** for FE-16
