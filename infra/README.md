# Infra — Docker & AWS Deployment

Everything needed to containerize and deploy WarrantyTrack.

```
infra/
├── docker/   → Dockerfiles for frontend and backend.
│               (docker-compose.yml lives at the repo root for local dev.)
└── aws/      → AWS deployment notes/configs: ECS task definitions, ALB,
                RDS, S3, Cognito, SES setup. Deployment runbook.
```

## Local containers

From the **repo root** (not here):

```bash
docker compose up --build
```

Note the build context is the **repo root**, not `./backend` or `./frontend` —
that's why the Dockerfiles `COPY backend/...` rather than `COPY ...`. A root
`.dockerignore` keeps `node_modules`, `.env` files and `.git` out of the images.

Each Dockerfile has two targets:

| Target | Used by | Behaviour |
|---|---|---|
| `dev` | docker compose | Hot reload, source mounted from your machine |
| `prod` | ECR / ECS | Production build, code baked into the image |

## AWS deployment (target architecture)

- **ECS Fargate** runs the containerized app (frontend + backend).
- **ALB** distributes traffic across AZs.
- **ECR** stores the Docker images ECS pulls.
- **RDS PostgreSQL** for the database.
- **S3** stores receipts/invoices; **Textract** extracts data.
- **Cognito** for auth; **SES** for expiry emails; **CloudWatch** for logs.

Region: `ap-southeast-1` (Singapore).

## Cost control — read this before creating anything

The budget is **฿4,000 for the whole semester**. An always-on Multi-AZ setup
costs roughly that *per month*, so the design deliberately trades availability
for cost:

| Decision | Why |
|---|---|
| **No NAT Gateway** | ~$33/month by itself. Run ECS tasks in public subnets with security groups that only accept traffic from the ALB, and add the free **S3 gateway VPC endpoint**. Interface endpoints cost more than the NAT — don't use them to avoid it. |
| **Single-AZ RDS** | Multi-AZ doubles the database bill. Document Multi-AZ as the production choice in the report instead. |
| **One task per service** | Scale to two only for the demo. |
| **Stop the stack when idle** | Nothing needs to run overnight. |

**Do first, before creating any resource:** set an **AWS Budgets** alert at
฿2,000 so we find out early rather than at the end of the semester.

## Things that will bite us (plan ahead)

- **SES starts in sandbox mode** — you can only email *verified* addresses,
  capped around 200/day. Leaving sandbox needs a support request that can take
  a day or more. **Verify all five team emails early.**
- **Migrations on ECS** — run `alembic upgrade head` as a one-off ECS task
  during deploy. Don't put it in the container entrypoint, or multiple starting
  tasks will race each other.
- **Secrets** — use **SSM Parameter Store** (free at standard tier) via the
  task definition's `secrets` block. Not `.env` files, not Secrets Manager.
- **Expiry emails** must be a scheduled job (EventBridge Scheduler → ECS
  RunTask), not an in-process timer — with more than one task running, an
  in-process scheduler sends duplicate emails.

Document every manual AWS step in `aws/DEPLOYMENT.md` so anyone on the team can
reproduce or tear down the environment.
