# infra/aws — Terraform for the AWS deployment

Infrastructure as code for the target architecture in
[`docs/architecture.md`](../../docs/architecture.md) and the service list and
cost rules in [`infra/README.md`](../README.md).

Step-by-step commands are in [`DEPLOYMENT.md`](DEPLOYMENT.md).

## What this creates

| Service | Purpose |
|---|---|
| **VPC** | `10.0.0.0/16`, 2 public + 2 private subnets across 2 AZs, internet gateway, S3 gateway endpoint. **No NAT gateway.** |
| **Security groups** | ALB:80 from the internet → task:3000 from the ALB only → RDS:5432 from the task only |
| **ALB** | Public entry point, one target group on the web container's port 3000 |
| **ECS Fargate** | Cluster, a two-container task (`web` + `api`), the service, and a separate job task definition for migrations |
| **ECR** | Two repositories with scan-on-push and a 10-image lifecycle policy |
| **RDS PostgreSQL** | Single-AZ, encrypted, private, 7-day backups. No final snapshot — see DEPLOYMENT.md teardown. |
| **Cognito** | User pool and public browser client |
| **SSM Parameter Store** | `DATABASE_URL` and `SECRET_KEY` as SecureStrings; `TAVILY_API_KEY` too when the warranty lookup is on |
| **CloudWatch Logs and alarms** | `/ecs/<name>` with 14-day retention; ALB health, ECS CPU and RDS free-storage alarms |
| **SNS** | Email notifications for CloudWatch alarms; the recipient must confirm the subscription |
| **IAM** | Scoped execution and task roles plus a main-branch GitHub OIDC deployment role |
| **AWS Budgets** | Monthly alert at 50%, 80% and forecast 100% |
| **S3** | Private receipts bucket, encryption, public access block, browser CORS, and upload cleanup |
| **SES** | Sender identity and optional recipient identities; inbox owners must complete verification |
| **EventBridge Scheduler** | Daily one-off Fargate warranty scan; disable it until email is ready |
| **Bedrock integration** | OCR model configuration and task IAM permission; model access is configured in the AWS account |

After the first Terraform apply, the `main` branch's GitHub Actions workflow
builds SHA-tagged images and deploys them to ECS after frontend and backend CI
pass. It uses short-lived OIDC credentials, runs migrations before switching
the service task definition, and checks `/api/health`. Terraform continues to
manage infrastructure; the deployment script owns new ECS task revisions.

## What this deliberately does not create

| Not here | Owner |
|---|---|
| **SES identity verification** | Terraform creates identity requests, but the inbox owner must click the verification link. Sandbox recipients must also be verified. |
| **Bedrock model access** | Select an available model or inference profile, enable access for the account, and set `bedrock_model_id`. |
| **HTTPS / ACM certificate** | Needs a domain, and none has been chosen — see [`docs/REQUIRES_YOUR_INPUT.md`](../../docs/REQUIRES_YOUR_INPUT.md). Traffic is HTTP only, so use test accounts and no real personal data. |

## Two design decisions worth knowing

### The browser reaches the API same-origin

The API serves `/health`, `/assets` and `/dashboard` at its **root**, and the
Next.js frontend serves pages at those same paths. Path-based routing on the
load balancer would therefore be ambiguous.

Instead the web container rewrites `/api/*` to the api container on
`127.0.0.1:8000`, stripping the prefix:

```
Browser ─→ ALB:80 ─→ web:3000 ──/api/* rewrite──→ api:8000
```

That lets `NEXT_PUBLIC_API_URL` be a relative `/api`, which means **no CORS**
and **no need to know the load balancer hostname at image build time**. The
rewrite lives in `frontend/next.config.ts`; local development is unaffected,
because `.env.local` points `NEXT_PUBLIC_API_URL` straight at
`http://localhost:8000` and bypasses it.

Port 8000 is absent from every security group on purpose — nothing outside the
task needs to reach it.

### Cognito is applied before the web image is built

Next inlines `NEXT_PUBLIC_*` values at build time, so the web image cannot be
built until the Cognito client ID exists. Cognito, ECR and the budget alert are
all free, so they are applied first; you read the outputs, build and push, and
only then create the chargeable resources. `DEPLOYMENT.md` sets this out as an
ordered sequence.

## Cost

No NAT gateway (~USD 33/month saved), single-AZ RDS, one task, and an ECR
lifecycle policy. The budget alert is created first because
[`infra/README.md`](../README.md) says to do that before creating any resource.

**Tear the stack down when not demoing.** `desired_count = 0` stops Fargate but
the ALB and RDS keep billing — a load balancer has no stop operation.

## Learner Lab testing

The stack targets a real AWS account. To rehearse in an AWS Academy Learner Lab
first, start from `terraform.tfvars.lab.example`, which sets
`create_iam_roles = false` (labs deny `iam:CreateRole`) and
`use_container_database = true` (labs usually deny `rds:CreateDBInstance`).

The container database stores data on the task's ephemeral disk, so **all data
is lost whenever the task restarts.** It exists to prove the deployment shape,
never for a real deployment.

## Files

```
versions.tf        provider pins and default tags
variables.tf       the full input surface
main.tf            data sources, locals, the backend's environment contract
network.tf         VPC, subnets, routing, S3 endpoint
security.tf        the three security groups
identity.tf        Cognito user pool and client
registry.tf        ECR repositories and lifecycle policies
secrets.tf         generated DATABASE_URL and SECRET_KEY in SSM
warranty_search.tf optional Tavily key parameter for the online warranty lookup
storage.tf         private S3 bucket, CORS, encryption, and lifecycle
ses.tf             SES sender and optional recipient identities
scheduler.tf       EventBridge Scheduler and its ECS invocation role
bedrock.tf         OCR backend and Bedrock model inputs
database.tf        RDS PostgreSQL
load_balancer.tf   ALB, target group, listeners
ecs.tf             cluster, task definitions, service
iam.tf             execution and task roles
github_deploy.tf   GitHub OIDC provider and scoped ECS/ECR deploy role
monitoring.tf      SNS alert topic and CloudWatch alarms
deploy-ecs.sh      migrate, switch ECS task revision, verify health
budget.tf          AWS Budgets alert
outputs.tf         everything the deploy steps and the frontend build need
```
