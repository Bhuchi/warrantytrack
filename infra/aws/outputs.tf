output "app_url" {
  description = "Public URL of the application."
  value       = local.app_url
}

output "health_url" {
  value = "${local.app_url}/api/health"
}

output "aws_region" {
  value = var.aws_region
}

output "cognito_user_pool_id" {
  description = "Set as COGNITO_USER_POOL_ID on the backend."
  value       = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  description = "Build the web image with NEXT_PUBLIC_COGNITO_CLIENT_ID set to this."
  value       = aws_cognito_user_pool_client.web.id
}

output "api_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "web_repository_url" {
  value = aws_ecr_repository.web.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.app.name
}

output "job_task_definition_arn" {
  description = "Run this with aws ecs run-task to apply migrations."
  value       = aws_ecs_task_definition.job.arn
}

output "app_subnet_ids" {
  description = "Subnets for the run-task network configuration."
  value       = aws_subnet.public[*].id
}

output "app_security_group_id" {
  value = aws_security_group.app.id
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.app.name
}

output "database_mode" {
  description = "rds for a real deployment; container only in a lab account that denies RDS."
  value       = var.use_container_database ? "container" : "rds"
}

output "database_endpoint" {
  value = var.use_container_database ? "127.0.0.1:5432 (in-task container)" : one(aws_db_instance.main[*].endpoint)
}
