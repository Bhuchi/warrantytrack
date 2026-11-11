# Robot Framework UI tests

End-to-end tests that drive the web app in Chrome, one suite per user journey
(CLOUDAPPG5-134). Their `report.html` and `log.html` go into the Testing Report.

| Suite | Journey |
|---|---|
| `add_asset.robot` | Sign in, choose a workspace, add an asset from a receipt, find it in the list |

## Run locally

Start the app first (`docker compose up`, then `docker compose exec backend python -m scripts.seed_dev` once).
Locally `AUTH_BACKEND=dev` skips Cognito, so any email and password sign in.

```bash
cd tests/robot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
robot --outputdir results add_asset.robot
open results/report.html
```

Chrome must be installed. Selenium downloads the matching driver by itself.
Add `--variable BROWSER:chrome` to watch the browser instead of running it headless.

## Run against AWS

Use the deployed URL and a Cognito test account that has `email_verified=true`:

```bash
robot --outputdir results \
  --variable URL:https://<deployed-url> \
  --variable EMAIL:<test-account-email> \
  --variable PASSWORD:<test-account-password> \
  add_asset.robot
```

`results/` is git-ignored. Never commit a real password; pass it on the command line.
