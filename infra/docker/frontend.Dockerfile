# Frontend image (Next.js).
# Build context is the REPO ROOT, not ./frontend — see docker-compose.yml.
#
# Two targets:
#   dev  → next dev with hot reload (used by docker compose)
#   prod → production build, pushed to ECR and run on ECS Fargate

FROM node:22-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS dev
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM node:22-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production

# Next inlines NEXT_PUBLIC_* at BUILD time, so these must be present before
# `npm run build` — setting them on the ECS task definition is too late and the
# deployed app would fall back to http://localhost:8000.
#
# NEXT_PUBLIC_API_URL stays relative: the web container rewrites /api/* to the
# api container, so the browser never needs the load balancer hostname.
# NEXT_PUBLIC_COGNITO_CLIENT_ID comes from `terraform output cognito_client_id`.
ARG NEXT_PUBLIC_API_URL=/api
ARG NEXT_PUBLIC_COGNITO_CLIENT_ID=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_COGNITO_CLIENT_ID=$NEXT_PUBLIC_COGNITO_CLIENT_ID

COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
