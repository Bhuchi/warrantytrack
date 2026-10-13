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
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
