# Backend image (FastAPI).
# Build context is the REPO ROOT, not ./backend — see docker-compose.yml.
#
# Two targets:
#   dev  → auto-reloads on file change (used by docker compose)
#   prod → what gets pushed to ECR and run on ECS Fargate

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
