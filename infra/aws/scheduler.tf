# Daily warranty-expiry scan (CLOUDAPPG5-98).
#
# EventBridge Scheduler starts a one-off Fargate task, not a timer inside the
# API: with more than one API task an in-process scheduler would email every
# recipient once per task (infra/README.md). The task is the existing "job"
# definition from ecs.tf with its command overridden to run the scan.
#
# backend/scripts/scan_warranties.py is run as a module from /app, which is the
# image's WORKDIR (infra/docker/backend.Dockerfile).

variable "scan_schedule_expression" {
  description = "EventBridge cron for the scan, evaluated in scan_schedule_timezone. Default is 08:00 every day."
  type        = string
  default     = "cron(0 8 * * ? *)"
}

variable "scan_schedule_timezone" {
  description = "IANA timezone for scan_schedule_expression."
  type        = string
  default     = "Asia/Bangkok"
}

variable "scan_schedule_enabled" {
  description = "Set false to keep the schedule defined but paused, e.g. while SES is still in sandbox."
  type        = bool
  default     = true
}

# The role Scheduler assumes to call ecs:RunTask. Skipped in a Learner Lab,
# which denies role creation; LabRole must then trust scheduler.amazonaws.com.
data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  count              = var.create_iam_roles ? 1 : 0
  name               = "${var.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

resource "aws_iam_role_policy" "scheduler" {
  count = var.create_iam_roles ? 1 : 0
  name  = "${var.name}-run-scan-task"
  role  = aws_iam_role.scheduler[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ecs:RunTask"]
        # Family ARN without a revision, so it matches whichever revision the
        # schedule resolves to.
        Resource = ["${aws_ecs_task_definition.job.arn_without_revision}:*"]
        Condition = {
          ArnEquals = { "ecs:cluster" = aws_ecs_cluster.main.arn }
        }
      },
      {
        # Required to hand the task its execution and task roles.
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [local.execution_role_arn, local.task_role_arn]
        Condition = {
          StringLike = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
        }
      }
    ]
  })
}

locals {
  scheduler_role_arn = var.create_iam_roles ? aws_iam_role.scheduler[0].arn : data.aws_iam_role.existing[0].arn
}

resource "aws_scheduler_schedule" "warranty_scan" {
  name                         = "${var.name}-warranty-scan"
  description                  = "Daily warranty-expiry scan: creates notifications and sends SES email."
  state                        = var.scan_schedule_enabled ? "ENABLED" : "DISABLED"
  schedule_expression          = var.scan_schedule_expression
  schedule_expression_timezone = var.scan_schedule_timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = local.scheduler_role_arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.job.arn_without_revision
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        subnets          = aws_subnet.public[*].id
        security_groups  = [aws_security_group.app.id]
        assign_public_ip = true # no NAT gateway; see ecs.tf
      }
    }

    # RunTask overrides: swap the job definition's default `alembic upgrade
    # head` for the scan.
    input = jsonencode({
      containerOverrides = [{
        name    = "api"
        command = ["python", "-m", "scripts.scan_warranties"]
      }]
    })

    # A missed run is not worth retrying for hours; the scan is idempotent and
    # tomorrow's run covers it.
    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600
    }
  }
}
