# Infra — Docker & AWS Deployment

Everything needed to containerize and deploy WarrantyTrack.

```
infra/
├── docker/   → Dockerfiles for frontend and backend, plus any shared config.
│               (docker-compose.yml lives at the repo root for local dev.)
└── aws/      → AWS deployment notes/configs: ECS task definitions, ALB,
                RDS, S3, Cognito, SES setup. Deployment runbook.
```

## Local containers

From the **repo root** (not here):

```bash
docker compose up --build
```

This builds the frontend and backend images and starts them alongside a local
PostgreSQL container. See the compose file for service definitions.

## AWS deployment (target architecture)

- **ECS Fargate** runs the containerized app (frontend + backend).
- **ALB** distributes traffic across AZs.
- **ECR** stores the Docker images ECS pulls.
- **RDS PostgreSQL (Multi-AZ)** for the database.
- **S3** stores receipts/invoices; **Textract** extracts data.
- **Cognito** for auth; **SES** for expiry emails; **CloudWatch** for logs.

Region: `ap-southeast-1` (Singapore).

> ⚠️ Keep the ฿4,000 budget in mind — tear down non-essential resources when not
> demoing. Document every manual AWS step in `aws/DEPLOYMENT.md` so anyone on the
> team can reproduce or clean up the environment.
