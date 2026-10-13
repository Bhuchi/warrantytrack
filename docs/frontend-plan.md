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

## Before touching the Jira board

This file is a **plan**, not a mirror of the board. The board moves on its own —
other people add issues, rename them, change statuses, and the keys quoted here
may be wrong by the time you read it. **Read the board first, then reconcile.**

1. **List what actually exists.** `searchJiraIssuesUsingJql` with
   `project = CLOUDAPPG5 ORDER BY created ASC`. Do not assume any key in this
   file is still correct.
2. **Match by summary text, not by key.** The keys quoted below
   (CLOUDAPPG5-13, -14, -115) came from a screenshot on 14 Oct 2026. If an
   issue with the same summary already exists under a different key, edit it —
   do not create a duplicate.
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

1. Every issue needs a **Start date** and a **Due date** — both, not just due.
2. Every issue must be **linked to an Epic**. Timeline draws one bar per epic
   and nests children inside it.
3. Give each **Epic** its own start/due spanning its children.
4. On a Kanban board, enable the Timeline view in Board settings if it is hidden.

## Epics

Named after the Functional Requirements headings in the Kick-off Report, so the
board maps onto the report one-to-one. Backend tickets belong in the same epics.

| Epic | Covers | Start | Due |
|---|---|---|---|
| Design System & App Shell | Shared UI, navigation, responsive foundation | 14 Oct | 24 Oct |
| User Management System | Auth screens, workspace selection, session wiring | 14 Oct | 31 Oct |
| Product / Asset Management | Assets list, asset detail, dashboard | 20 Oct | 7 Nov |
| Document and OCR Management | Add Asset wizard, OCR review | 27 Oct | 10 Nov |
| Warranty Notification | Notifications screen, settings, toasts | 3 Nov | 12 Nov |
| Release & QA | Integration, responsive QA, demo prep | 10 Nov | 17 Nov |

## Done already

| Key | Summary | Status |
|---|---|---|
| CLOUDAPPG5-115 | Scaffold Next.js frontend + landing page (D01 / M01) | Done |
| CLOUDAPPG5-13 | Login / Sign Up screen (D02 / M02) | Done |
| CLOUDAPPG5-14 | Workspace Selection screen (D03 / M03) | Done |

> All three are UI-only — no screen talks to the API yet. Wiring is tracked
> separately below so the board does not overstate progress.

## Tickets to create

Build order is mobile frame first, then `md:` overrides for desktop.

### Design System & App Shell

**FE-01 · Build shared UI component library**
- Assignee: Earth · Start 14 Oct · Due 17 Oct
- Extract `Button`, `StatusBadge`, `Card`, `Modal`, `Toast` into `components/`
  from the patterns already repeated across D01–D03.
- AC: each has a mobile and `md:` desktop variant; `StatusBadge` renders
  Active / Expiring Soon / Expired / No warranty; no raw hex outside
  `app/globals.css`.

**FE-02 · Build navigation panel and signed-in app shell (M10)**
- Assignee: Earth · Start 17 Oct · Due 22 Oct
- Figma `3392:2` and `3455:536`. Drawer nav for mobile, sidebar for desktop
  (`3382:1309`). Includes sign-out, which mobile currently has nowhere.
- AC: route group for signed-in screens; nav highlights the current route;
  drawer traps focus and closes on Escape and on backdrop tap.

**FE-03 · Loading, empty and error states**
- Assignee: Bright · Start 20 Oct · Due 24 Oct
- AC: a skeleton, an empty state and an error state usable by every list and
  detail screen; `ApiError` messages surface to the user rather than the console.

### User Management System

**FE-04 · Wire auth screens to Cognito**
- Assignee: Earth · Start 24 Oct · Due 31 Oct
- Blocked by: backend Cognito setup + `/auth` endpoints.
- AC: sign in, sign up and sign out work end to end; token supplied through
  `setAuthTokenProvider` in `lib/api`; unauthenticated users are redirected;
  form validation and server errors shown inline.

**FE-05 · Wire workspace selection to the API**
- Assignee: Earth · Start 28 Oct · Due 31 Oct
- Blocked by: backend `/workspaces` endpoint.
- AC: real workspaces and counts replace the Figma placeholders; the chosen
  workspace persists and scopes every later request.

### Product / Asset Management

**FE-06 · Build Dashboard (D04 / M04)**
- Assignee: Bright · Start 20 Oct · Due 27 Oct
- Figma `3382:141`, `3418:385`. Summary counts, warranty status breakdown.
- AC: shows active / expiring soon / expired / no-warranty totals; org view
  can group by department, location, category, vendor; mock data behind a
  single function so swapping to the API is one change.

**FE-07 · Build Assets List with search and filters (D05 / M05)**
- Assignee: Bright · Start 27 Oct · Due 3 Nov
- Figma `3382:296`, `3418:524`, filters `3396:7503`.
- AC: filter by warranty status; search by name and serial; empty state;
  list virtualises or paginates past 50 rows.

**FE-08 · Build Asset Detail (D08 / M08)**
- Assignee: Bright · Start 3 Nov · Due 7 Nov
- Figma `3382:676`, `3455:318`.
- AC: shows warranty dates and computed status, attached documents, and the
  box/storage photo and note from Add Asset step 3.

### Document and OCR Management

**The Add Asset flow**, agreed 14 Oct. Three steps, each ending in
edit → confirm / cancel:

```
Add Asset
├─ 1. Receipt / invoice          REQUIRED — no skip
│     OCR the receipt, or enter manually. Manual is offered up front
│     and automatically when OCR fails. This is the information that
│     identifies the asset, so the step must produce data either way.
├─ 2. Serial number              OPTIONAL — skippable
│     OCR it, type it, or skip. Not every warranty needs one.
└─ 3. Box / storage photo        OPTIONAL — skippable
      Photo of the box or where it is kept, plus a free-text note.
      Shown later on Asset Detail, for warranties that need the box.
```


**FE-09 · Add Asset step 1 — receipt (D06 / M06)**
- Assignee: Earth · Start 27 Oct · Due 2 Nov
- Figma `3382:447`, `3436:1771`, stepper `3396:7449`.
- **This step cannot be skipped.** It carries the information that identifies
  the asset, so there is no Skip control — only two ways in:
  1. **OCR** — upload or capture the receipt, Textract fills the fields, the
     user edits and confirms.
  2. **Enter manually** — available up front, and offered automatically when
     OCR fails or returns nothing usable.
- AC: no Skip control anywhere on this step; "Enter manually" is reachable
  without first attempting OCR; camera capture works on mobile; every OCR
  field is editable before confirm; required fields are validated before
  Confirm enables; cancel discards the whole wizard without saving.

**FE-10 · Add Asset step 2 — serial number, optional**
- Assignee: Earth · Start 2 Nov · Due 5 Nov
- OCR the serial, or type it, or skip entirely.
- AC: a visible **Skip** control; skipping still saves the asset; a hint
  explains some warranties need a serial at claim time.

**FE-11 · Add Asset step 3 — box / storage photo, optional**
- Assignee: Earth · Start 5 Nov · Due 8 Nov
- Photo of the box or where it is stored, plus a free-text note.
- AC: both fields optional and skippable; photo and note appear on Asset Detail.

**FE-12 · Build OCR Review screen (D07 / M07)**
- Assignee: Earth · Start 3 Nov · Due 10 Nov
- Figma `3382:566`, `3455:225`.
- AC: extracted values shown beside the source image; low-confidence fields
  flagged; user can correct every field; confirm writes the verified values.

### Warranty Notification

**FE-13 · Build Notifications screen (D09 / M09)**
- Assignee: Bright · Start 7 Nov · Due 11 Nov
- Figma `3382:794`, `3455:421`, plus in-page notification `3488:171` and
  toast variants `3488:286`.
- AC: list of expiry notifications; read/unread; toast on asset saved.

**FE-14 · Build Settings — notifications (M11 / M12)**
- Assignee: Bright · Start 10 Nov · Due 12 Nov
- Figma `3464:171`, `3468:171`, `3494:171` (organization, scrolled).
- AC: personal and organization variants; toggles persist.

### Release & QA

**FE-15 · Responsive and accessibility QA pass**
- Assignee: Earth · Start 11 Nov · Due 14 Nov
- AC: every screen checked at 402 px and 1440 px on a real device; no
  horizontal scroll; tap targets ≥ 44 px; labels on all inputs; keyboard
  navigation works; colour contrast checked against the brand blue.

**FE-16 · Frontend integration with deployed backend**
- Assignee: Earth + Bright · Start 12 Nov · Due 16 Nov
- Blocked by: ECS deployment.
- AC: `NEXT_PUBLIC_API_URL` points at the ALB; every screen runs on real data;
  no mock data left in the bundle.

**FE-17 · Demo script and report screenshots**
- Assignee: Earth · Start 14 Nov · Due 17 Nov
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
