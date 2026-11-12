resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.name}"
  retention_in_days = 14
}

resource "aws_ecs_cluster" "main" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = "disabled" # chargeable, and not needed at this scale
  }
}

locals {
  api_container = {
    name      = "api"
    image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    environment = local.api_environment
    secrets     = local.api_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
  }

  web_container = {
    name      = "web"
    image     = "${aws_ecr_repository.web.repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 3000
      hostPort      = 3000
      protocol      = "tcp"
    }]
    # Read by the rewrite in frontend/next.config.ts. Both containers share the
    # task's network namespace, so the API is on loopback.
    environment = [
      { name = "API_INTERNAL_URL", value = "http://127.0.0.1:8000" }
    ]
    dependsOn = [{ containerName = "api", condition = "START" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "web"
      }
    }
  }

  # Lab only. See the use_container_database variable.
  db_container = {
    name      = "db"
    image     = "public.ecr.aws/docker/library/postgres:17-alpine"
    essential = true
    environment = [
      { name = "POSTGRES_DB", value = local.db_name },
      { name = "POSTGRES_USER", value = local.db_user }
    ]
    secrets = var.use_container_database ? [{
      name      = "POSTGRES_PASSWORD"
      valueFrom = one(aws_ssm_parameter.db_password[*].arn)
    }] : []
    healthCheck = {
      command     = ["CMD-SHELL", "pg_isready -U ${local.db_user} -d ${local.db_name}"]
      interval    = 10
      timeout     = 5
      retries     = 10
      startPeriod = 30
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "db"
      }
    }
  }

  # Lab only: with no reachable RDS there is nowhere for a standalone migration
  # task to connect, so migrations run in-task before the API starts.
  migrate_container = {
    name        = "migrate"
    image       = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential   = false
    command     = ["alembic", "upgrade", "head"]
    environment = local.api_environment
    secrets     = local.api_secrets
    dependsOn   = [{ containerName = "db", condition = "HEALTHY" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "migrate"
      }
    }
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.task_cpu)
  memory                   = tostring(var.task_memory)
  execution_role_arn       = local.execution_role_arn
  task_role_arn            = local.task_role_arn

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = var.use_container_database ? jsonencode([
    local.db_container,
    local.migrate_container,
    merge(local.api_container, {
      dependsOn = [{ containerName = "migrate", condition = "SUCCESS" }]
    }),
    local.web_container
  ]) : jsonencode([local.api_container, local.web_container])

  depends_on = [
    aws_iam_role_policy_attachment.execution,
    aws_iam_role_policy.execution_secrets
  ]
}

# Run with `aws ecs run-task` during deploy. Migrations are deliberately not in
# the container entrypoint: with more than one task starting, they would race
# each other. See infra/README.md.
resource "aws_ecs_task_definition" "job" {
  family                   = "${var.name}-job"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.task_cpu)
  memory                   = tostring(var.task_memory)
  execution_role_arn       = local.execution_role_arn
  task_role_arn            = local.task_role_arn

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    merge(local.api_container, {
      command = ["alembic", "upgrade", "head"]
    })
  ])

  depends_on = [
    aws_iam_role_policy_attachment.execution,
    aws_iam_role_policy.execution_secrets
  ]
}

resource "aws_ecs_service" "app" {
  name            = var.name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # The health check traverses web, then the rewrite, then api. Without a grace
  # period ECS can kill a task that is only still starting up.
  health_check_grace_period_seconds = 60

  # No NAT gateway, so the task needs a public IP to pull images and reach
  # Cognito, S3, Bedrock and SES. The security group limits inbound traffic.
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.http]
}
