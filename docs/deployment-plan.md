# WarrantyTrack AWS deployment plan

This is the checklist for deploying the application in this repository. Use the exact commands and troubleshooting steps in the [AWS deployment runbook](../infra/aws/DEPLOYMENT.md). Review each Terraform plan before its apply; a successful apply alone does not prove that application features work.

## Current starting point (10 November 2026)

- [x] Terraform configuration and Dockerfiles exist. Terraform, AWS CLI, Docker, and `jq` are installed; the Docker daemon responds; `terraform fmt -check -recursive infra/aws` passes.
- [x] The group reports an AWS account with a THB 4,000 project budget and permission to create IAM roles. Use the real-account configuration with `create_iam_roles = true`; verify the actual permissions during preflight.
- [ ] `infra/aws/terraform.tfvars` is configured. It is currently absent from this checkout.
- [ ] AWS CLI credentials are valid. The current read-only STS check returns `InvalidClientTokenId`; refresh the project's credentials securely before planning.
- [ ] Terraform initialization and AWS permissions are verified. This checkout has no `.terraform` provider directory or local Terraform state yet.
- [ ] AWS resources and the application are deployed. No deployment has been verified during this review.
- [ ] Application integration is complete. The backend currently registers only `/health`; sign-in does not submit, and dashboard and receipt scan use mock data.

The existing application can support a **deployment smoke test** of the homepage and `/api/health`. A complete user workflow needs the backend endpoints and frontend integration first.

## 1. Choose the target account and protect the state

- [x] Select the group's AWS account as the deployment target. Check its permitted region and services before planning.
- [ ] Start from the real-account [`terraform.tfvars.example`](../infra/aws/terraform.tfvars.example): `ap-southeast-1`, private RDS PostgreSQL, and Terraform-managed IAM roles (`create_iam_roles = true`). Terraform creates separate `warrantytrack-execution` and `warrantytrack-task` roles; there is no need to create them manually.
- [ ] For Learner Lab, start from [`terraform.tfvars.lab.example`](../infra/aws/terraform.tfvars.lab.example): typically `us-east-1`, existing `LabRole`, and an in-task PostgreSQL container. **Lab database data is lost on task restart.** Confirm the lab's actual permissions; its Budgets API may be unavailable.
- [ ] Choose one deployment operator or a shared Terraform state arrangement before teammates run `apply`. The current configuration uses local state, which contains sensitive values and is ignored by Git.

**Gate:** Account, region, permissions, state owner, and database mode are agreed.

## 2. Gather inputs and validate locally

- [ ] Confirm AWS identity with `aws sts get-caller-identity`; confirm Docker is running and Terraform, AWS CLI, and `jq` are available.
- [ ] Obtain the document bucket name from the S3/Textract workstream and a budget alert email. Set `ses_sender_email`, noting that SES verification must be completed separately before email can work.
- [ ] Set `budget_limit_usd` for the group's THB 4,000 **total project budget**. The Terraform budget resets monthly and sends alerts; it is not a spending cap. Check the current exchange rate and remaining project duration before choosing its monthly amount.
- [ ] Copy the appropriate example to `infra/aws/terraform.tfvars`, fill in real values, and keep that file and AWS credentials out of Git and chat.
- [ ] Run `terraform fmt -check -recursive infra/aws`, `terraform -chdir=infra/aws init`, and `terraform -chdir=infra/aws validate`.
- [ ] Run the repository's frontend and backend CI checks or local equivalents before building deployment images.

**Gate:** Inputs are complete, tools work, validation passes, and the team knows which features are still mocks.

## 3. Create the foundation first

- [ ] From `infra/aws`, make the Phase 1 targeted plan in the [runbook](../infra/aws/DEPLOYMENT.md#phase-1--foundation-free). It creates the Cognito client, two ECR repositories, and the budget alert.
- [ ] Review the planned account, region, resource names, IAM effects, and budget settings. Apply the saved plan only after that review.
- [ ] Record `cognito_client_id` and both ECR repository URLs. The frontend image needs the Cognito client ID **at build time**.

**Gate:** Cognito and ECR outputs exist in the intended account. ECR image storage can incur charges after images are pushed.

## 4. Build and push both images

- [ ] Build the backend and frontend production images for `linux/amd64` using the repository root as build context.
- [ ] Build the frontend with `NEXT_PUBLIC_API_URL=/api` and the Phase 1 Cognito client ID.
- [ ] Give both images the same unique tag, push them to ECR, and verify the tag exists in both repositories.

**Gate:** Both image URIs and the tag are known. See [Phase 2 commands](../infra/aws/DEPLOYMENT.md#phase-2--build-and-push).

## 5. Create the application infrastructure without starting tasks

- [ ] Plan the remaining stack with that image tag and `desired_count=0`.
- [ ] Review the full plan and expected running costs before applying. This phase creates the VPC, security groups, ALB, ECS definitions, SSM parameters, and either RDS or the lab database mode.
- [ ] Apply the saved plan. ALB and RDS can accrue charges even while ECS has zero running tasks.

**Gate:** Terraform outputs exist, the stack matches the selected account/mode, and no ECS service task is running yet. See [Phase 3](../infra/aws/DEPLOYMENT.md#phase-3--the-rest-of-the-stack).

## 6. Migrate and start one task

- [ ] **Real-account RDS mode:** run the one-off ECS migration task and confirm it exited with code `0` before starting the service.
- [ ] **Learner Lab container database mode:** skip the separate migration task; the service task's `migrate` container runs the migration before the API starts.
- [ ] Plan and apply `desired_count=1` with the same image tag. Keep `image_tag` and `desired_count=1` in `terraform.tfvars` so a later plain apply does not revert them.

**Gate:** The ECS service has a healthy target. See [Phase 4](../infra/aws/DEPLOYMENT.md#phase-4--migrate-then-start).

## 7. Verify, integrate, and record evidence

- [ ] Check the ALB URL, `/api/health`, homepage, target health, ECS events, and API/web CloudWatch logs.
- [ ] Label this an **infrastructure smoke test** until the backend's feature routes and the frontend's authentication, dashboard, asset, and OCR wiring are complete.
- [ ] Once those features are implemented, test a real sign-in and user workflow with test accounts. The ALB currently serves **HTTP only**; do not use real personal data or tokens for a public demo until HTTPS is configured.
- [ ] Record the deployed URL, date, image tag, account mode, test results, and screenshots for the Final Report. Describe planned S3/Textract, SES, and scheduler integrations separately from verified behavior.

**Gate:** Report claims match observed tests, not just Terraform resources.

## 8. End the test and control costs

- [ ] Decide whether the environment needs to remain available. Scaling ECS to zero does **not** stop ALB or RDS billing.
- [ ] Before destroy, back up any data that must survive. The RDS configuration does not create a final snapshot; the Learner Lab container database is ephemeral.
- [ ] Review the destroy plan and repository contents. The ECR repositories do not set `force_delete`, so pushed images may need separate cleanup before the repositories can be destroyed.
- [ ] Destroy the stack when it is no longer needed, wait for completion, and verify billable resources are gone. Keep Terraform state until destroy has finished.

**Cost references:** [ALB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/), [RDS PostgreSQL pricing](https://aws.amazon.com/rds/postgresql/pricing/), and [ECR pricing](https://aws.amazon.com/ecr/pricing/). Actual charges depend on the account, region, usage, and applicable credits.
