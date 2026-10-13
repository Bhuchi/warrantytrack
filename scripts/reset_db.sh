#!/usr/bin/env bash
# Wipe the local database and re-apply all migrations from scratch.
# Useful when a migration goes wrong, or you want clean data.
#
# Usage (from the repo root):  ./scripts/reset_db.sh
#
# This destroys local data only. It never touches anything on AWS.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Stopping the stack and removing the database volume"
docker compose down -v

echo "==> Starting the database"
docker compose up -d db

echo "==> Waiting for PostgreSQL to accept connections"
until docker compose exec -T db pg_isready -U warranty -d warrantytrack >/dev/null 2>&1; do
  sleep 1
done

echo "==> Starting the backend and applying migrations"
docker compose up -d backend
docker compose exec -T backend alembic upgrade head

echo "==> Done. Database is empty and fully migrated."
