# Deployment runbook

How to deploy WarrantyTrack to AWS, tear it down, and diagnose it when it will
not start. For what the stack contains and why, see [`README.md`](README.md).

Every command runs from `infra/aws` unless stated otherwise.

## Prerequisites

- Terraform >= 1.11, AWS CLI v2, Docker, `jq`
- AWS credentials for the project account: `aws sts get-caller-identity`
- The **document bucket name** from the S3/Textract workstream
- A **verified SES sender**, or accept that mail will not send yet

```bash
cp terraform.tfvars.example terraform.tfvars
```

Fill in `document_bucket_name`, `ses_sender_email` and `budget_alert_email`.
Never commit `terraform.tfvars`.

## Why the order matters

Next.js inlines `NEXT_PUBLIC_*` at **build time**, so the web image cannot be
built until the Cognito user pool and client IDs exist. Deployment is therefore:

```
apply (free resources) → read outputs → build images → push → apply (the rest)
```

Phase 1 creates only what the image build consumes — the Cognito client and the
two ECR repositories, plus the budget alert. None of it is chargeable.

## Phase 1 — foundation (free)

```bash
terraform init
```

```bash
terraform plan -out=phase1.tfplan -target=aws_cognito_user_pool_client.web -target=aws_ecr_repository.api -target=aws_ecr_repository.web -target=aws_budgets_budget.monthly
```

Read the plan, then:

```bash
terraform apply phase1.tfplan
```

Collect the values the web image needs:

```bash
terraform output -raw cognito_user_pool_id && terraform output -raw cognito_client_id && terraform output -raw web_repository_url
```

> `-target` is a deliberate exception here, not a habit. It exists only to keep
> the chargeable resources out of this first apply.

## Phase 2 — build and push

Both Dockerfiles take the **repository root** as their build context, and both
use the `prod` target. Build for `linux/amd64`: Apple Silicon defaults to arm64
and the task definition pins X86_64, which otherwise fails with
`exec format error`.

From the repository root:

```bash
cd "$(git rev-parse --show-toplevel)" && export AWS_REGION=ap-southeast-1 ACCOUNT=$(aws sts get-caller-identity --query Account --output text) TAG=$(date -u +%Y%m%d%H%M%S) && echo "TAG=$TAG"
```

```bash
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
```

```bash
docker build --platform linux/amd64 --target prod -f infra/docker/backend.Dockerfile -t $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/warrantytrack-api:$TAG .
```

The web build needs both Cognito IDs from phase 1. `NEXT_PUBLIC_API_URL`
stays the relative `/api`, which is the Dockerfile default:

```bash
docker build --platform linux/amd64 --target prod -f infra/docker/frontend.Dockerfile --build-arg NEXT_PUBLIC_API_URL=/api --build-arg NEXT_PUBLIC_COGNITO_USER_POOL_ID=$(terraform -chdir=infra/aws output -raw cognito_user_pool_id) --build-arg NEXT_PUBLIC_COGNITO_CLIENT_ID=$(terraform -chdir=infra/aws output -raw cognito_client_id) -t $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/warrantytrack-web:$TAG .
```

```bash
docker push $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/warrantytrack-api:$TAG && docker push $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/warrantytrack-web:$TAG
```

## Phase 3 — the rest of the stack

This is where billing starts: the ALB and RDS. RDS takes 8–12 minutes.

```bash
cd infra/aws && terraform plan -var="image_tag=$TAG" -var="desired_count=0" -out=phase3.tfplan && terraform apply phase3.tfplan
```

`desired_count=0` on purpose — migrations have not run, so there is no schema
for the API to serve against yet.

## Phase 4 — migrate, then start

Migrations run as a **one-off task**, never in the container entrypoint: with
more than one task starting they would race each other.

> **Skip this phase entirely when `use_container_database = true`.** The database
> then lives inside the service task, on loopback, so a separate task has no way
> to reach it — `run-task` would fail to connect. In that mode the task's own
> `migrate` container applies migrations before the API starts, and the API waits
> on it succeeding. Check with `terraform output database_mode`.

```bash
cd infra/aws && aws ecs run-task --region "$(terraform output -raw aws_region)" --cluster "$(terraform output -raw ecs_cluster_name)" --task-definition "$(terraform output -raw job_task_definition_arn)" --launch-type FARGATE --network-configuration "{\"awsvpcConfiguration\":{\"subnets\":$(terraform output -json app_subnet_ids),\"securityGroups\":[\"$(terraform output -raw app_security_group_id)\"],\"assignPublicIp\":\"ENABLED\"}}" --query 'tasks[0].taskArn' --output text
```

Wait for it, then confirm it exited **0** before going further:

```bash
cd infra/aws && CL=$(terraform output -raw ecs_cluster_name) && T=$(aws ecs list-tasks --cluster $CL --desired-status STOPPED --query 'taskArns[0]' --output text) && aws ecs describe-tasks --cluster $CL --tasks $T --query 'tasks[0].containers[].{name:name,exit:exitCode,reason:reason}' --output table
```

A non-zero exit means the schema is not applied. Read the logs before starting
the service — do not skip ahead.

Now start one task:

```bash
cd infra/aws && terraform plan -var="image_tag=$TAG" -var="desired_count=1" -out=start.tfplan && terraform apply start.tfplan
```

Finally, put `image_tag` and `desired_count = 1` into `terraform.tfvars`, or the
next plain `terraform apply` scales back to zero and reverts the image tag.

## Verify

```bash
cd infra/aws && curl -sS "$(terraform output -raw health_url)" && echo && curl -sS -o /dev/null -w "homepage: %{http_code}\n" "$(terraform output -raw app_url)"
```

`{"status":"ok","service":"warrantytrack-api",...}` means the whole chain works:
ALB → web → the `/api/*` rewrite → api.

Load balancer's own view:

```bash
cd infra/aws && aws elbv2 describe-target-health --target-group-arn $(aws elbv2 describe-target-groups --names "$(terraform output -raw ecs_service_name)-web" --query 'TargetGroups[0].TargetGroupArn' --output text) --query 'TargetHealthDescriptions[].{ip:Target.Id,state:TargetHealth.State,reason:TargetHealth.Reason}' --output table
```

## Create the first user

Cognito authenticates; PostgreSQL authorizes. The backend accepts only a
verified Cognito **ID token** — an access token is rejected.

```bash
cd infra/aws && POOL=$(terraform output -raw cognito_user_pool_id) && aws cognito-idp admin-create-user --user-pool-id "$POOL" --username "you@example.com" --user-attributes Name=email,Value=you@example.com Name=email_verified,Value=true --message-action SUPPRESS && aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username "you@example.com" --password 'ChangeMe123!' --permanent
```

`email_verified=true` is not optional. Without it the user signs in to Cognito
successfully and then gets 401s from every API call, with nothing in the logs
to explain why.

## Redeploying

Repeat phase 2 with a new `$TAG`, run the migration task, then apply with that
tag. Migrations go **before** the new code serves traffic.

## Logs and diagnosis

```bash
aws logs tail /ecs/warrantytrack --since 15m --follow
```

One container only — streams are `api`, `web`, and `db`/`migrate` in lab mode:

```bash
aws logs tail /ecs/warrantytrack --log-stream-name-prefix api --since 30m
```

Why a task died:

```bash
cd infra/aws && CL=$(terraform output -raw ecs_cluster_name) && aws ecs describe-tasks --cluster $CL --tasks $(aws ecs list-tasks --cluster $CL --desired-status STOPPED --query 'taskArns[0]' --output text) --query 'tasks[0].{stopped:stoppedReason,containers:containers[].{name:name,exit:exitCode,reason:reason}}'
```

Scheduling problems that never produce a task:

```bash
cd infra/aws && aws ecs describe-services --cluster "$(terraform output -raw ecs_cluster_name)" --services "$(terraform output -raw ecs_service_name)" --query 'services[0].events[:5].message' --output text
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `exec format error` | Image built for arm64 | Rebuild with `--platform linux/amd64` |
| Container exits immediately, JSON parse error | `CORS_ORIGINS` is not a JSON array | Terraform writes `["http://..."]`; do not override it with a bare URL |
| `Can't load plugin: sqlalchemy.dialects:psycopg` | Wrong driver prefix | `DATABASE_URL` must start `postgresql://`, not `postgresql+psycopg://` |
| Deployed frontend calls `localhost:8000` | Web image built without build args | Rebuild passing `--build-arg NEXT_PUBLIC_API_URL=/api` |
| API 401 after a successful Cognito login | Access token sent, or `email_verified` false | Send the **ID** token; set `email_verified=true` |
| Target group unhealthy, task running | API not up, so the rewrite 502s | Read the `api` log stream |
| Task cycles start → stop | Migration never ran, or app crash | Confirm the job task exited 0 |
| `AccessDenied` on `aws_budgets_budget` | Learner Lab denies the budgets API | Use the lab's credit counter instead |
| `rds:CreateDBInstance` denied | Learner Lab | `use_container_database = true` for testing only |
| Plan wants to scale to 0 / revert the tag | `terraform.tfvars` out of sync | Set `image_tag` and `desired_count` |

## Teardown

```bash
terraform destroy
```

Expect 10–20 minutes. Most of it is AWS releasing the task's network interface,
which blocks the subnets and security groups behind it.

- **The database is deleted, with no final snapshot.** That is deliberate: the
  cost rules call for tearing the stack down between sessions, and a named
  snapshot makes the second teardown fail. Back up anything you need to keep
  before destroying.
- The **S3 bucket is not managed here** and survives, which is usually what you
  want: documents persist across rebuilds.
- Keep `terraform.tfstate` until destroy finishes, or you will be deleting
  resources by hand in the console.

Confirm nothing is still billing:

```bash
aws elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerName' --output text; aws rds describe-db-instances --query 'DBInstances[].DBInstanceIdentifier' --output text
```

Empty output from both means you are at zero.
