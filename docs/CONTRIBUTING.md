# Contributing: Git Workflow

Two long-lived branches and short-lived feature branches, everything merged
via reviewed Pull Requests:

- **`dev`** is where work comes together. Every feature branch starts from
  `dev` and is merged back into `dev`.
- **`main`** only receives merges from `dev`, when the team agrees `dev` is
  ready. Nobody opens a feature PR into `main`.

## The golden rules

1. **Never push directly to `dev` or `main`.** Both change only through PRs.
2. **One branch per task/ticket.** Small, focused PRs are easier to review.
3. **Every merge needs 1 approval + passing CI.**

## Step by step

```bash
# 1. Start from an up-to-date dev
git checkout dev
git pull origin dev

# 2. Create your branch
git checkout -b feat/assets-list-page

# 3. Work + commit in small chunks
git add .
git commit -m "feat: build asset row component (CLOUDAPPG5-85)"

# 4. Push
git push -u origin feat/assets-list-page

# 5. Open a Pull Request on GitHub into dev.
#    - Fill in the PR template
#    - Request a review from at least 1 teammate
#    - Wait for CI to pass

# 6. After approval → squash and merge → delete the branch.

# 7. Everyone else: pull dev to get the update
git checkout dev && git pull origin dev
```

## Branch naming

| Prefix | Use for | Example |
|---|---|---|
| `feat/` | new feature | `feat/ocr-review-screen` |
| `fix/` | bug fix | `fix/expiry-date-calc` |
| `chore/` | config, deps, docs, CI | `chore/add-eslint` |

Keep names short and kebab-case.

## Commit messages

Format: `<type>: <what changed> (<JIRA-KEY>)`

```
feat: add warranty status badge component (CLOUDAPPG5-84)
fix: correct expiry calculation off-by-one (CLOUDAPPG5-97)
chore: bump next.js to 14.2 (CLOUDAPPG5-65)
```

Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.

## Pull Requests

- Title includes the Jira key so tickets link automatically.
- Keep PRs small — ideally one screen or one endpoint per PR.
- Don't merge your own PR without a review.
- Resolve all review comments before merging.

## Handling conflicts

If `dev` moved ahead of your branch:

```bash
git checkout dev && git pull origin dev
git checkout your-branch
git merge dev         # resolve conflicts, commit, push
```

## Never commit

- `.env`, `.env.local`, or any file with secrets/keys
- `node_modules/`, `venv/`, build output
- AWS credentials

If you accidentally commit a secret, tell the team immediately and rotate the key.
