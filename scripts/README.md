# Scripts

Helper scripts for local development.

| Script | What it does |
|---|---|
| `reset_db.sh` | Drop, recreate and re-migrate the local database. |
| `run-aws-tests.sh` | Run the Robot and Postman tests against the AWS deployment. |

## Testing the AWS deployment

```bash
git switch main && git pull      # main is what is deployed
./scripts/run-aws-tests.sh          # both suites
./scripts/run-aws-tests.sh robot    # Robot only (browser, about 2 minutes)
./scripts/run-aws-tests.sh newman   # Postman only (API)
```

It asks for a Cognito test account's email and password. The password is not
shown, not saved, and kept out of the reports. Reports go to
`tests/robot/results/report.html` and `tests/postman/results/report.html`
(both git-ignored); open them with `open <path>`.

- Needs Python 3, Google Chrome and Node.js. The first Robot run sets up
  `tests/robot/.venv` by itself.
- Use a spare test account: each Postman run creates a "Postman Test Org"
  that cannot be deleted yet, and Robot adds one test asset per run.
- Testing a different deployment: `WT_URL=http://... ./scripts/run-aws-tests.sh`.

Suggested scripts to add as the project grows:

- `seed_db.py` → populate the local DB with sample assets/warranties for testing.
- `format.sh` → run formatters/linters across frontend and backend.

Keep scripts cross-platform where possible, or note the OS they target.
