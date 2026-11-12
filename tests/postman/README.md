# Postman API tests

`WarrantyTrack.postman_collection.json` calls every REST endpoint in
[`docs/api.md`](../../docs/api.md) and checks each response (CLOUDAPPG5-101).
35 requests in 9 folders, run in order: later requests reuse the ids that earlier
ones save (the asset created in folder 3 is edited, then deleted in folder 8).

| Folder | Checks |
|---|---|
| 0. Health | the API is up |
| 1. Account and workspaces | `GET /me`, picks the personal workspace; creating an organization |
| 2. Catalog | the four lists; create, duplicate name (409), rename, delete |
| 3. Assets | create, missing fields (422), duplicate serial (409), search, status filter, details, edit, assign refused in a personal workspace (422), unknown id (404) |
| 4. Bulk import | CSV dry run with one bad row |
| 5. Receipts and OCR | presign, upload `tests/robot/files/sample-receipt.png`, submit, read the extracted fields, confirm into an asset, confirm twice (409) |
| 6. Notifications | list, mark all read, unread becomes 0 |
| 7. Security | no token gives 401 (AWS only), another workspace's id gives 404 |
| 8. Clean up | deletes the assets it created |

A collection-level script adds `Authorization` and `X-Workspace-Id` to every
request, so no request sets them itself.

## Run locally

Start the backend (`docker compose up`, then `docker compose exec backend python -m scripts.seed_dev` once).
Locally `AUTH_BACKEND=dev` needs no token, and the personal workspace is picked from `GET /me`.

```bash
cd tests/postman
npx newman@6.2.1 run WarrantyTrack.postman_collection.json \
  -e environments/local.postman_environment.json --working-dir .
```

For an HTML report like the one in the Testing Report:

```bash
npx -p newman@6.2.1 -p newman-reporter-htmlextra@1.23.1 newman run WarrantyTrack.postman_collection.json \
  -e environments/local.postman_environment.json --working-dir . \
  --reporters cli,htmlextra --reporter-htmlextra-export results/report.html
```

Or in the Postman app: **Import** the collection and the environment, pick the
environment top right, then **Run collection**. The upload request needs the
receipt file: in the app, choose `tests/robot/files/sample-receipt.png` in its Body tab.

## Run against AWS

Set `baseUrl` in `environments/aws.postman_environment.json` to the deployed API
and pass a Cognito **ID token** of a test account on the command line (never
commit it):

```bash
npx newman@6.2.1 run WarrantyTrack.postman_collection.json \
  -e environments/aws.postman_environment.json --working-dir . \
  --env-var "token=<cognito-id-token>"
```

With a token, the "no token gives 401" check runs instead of being skipped.

Each run leaves one organization workspace named "Postman Test Org ..." behind,
because there is no endpoint to delete a workspace yet.
