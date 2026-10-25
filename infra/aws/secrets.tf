# Secrets come from SSM Parameter Store, free at standard tier — not from .env
# files and not from Secrets Manager. See docs/architecture.md.
#
# Both values are generated as ephemeral resources and written with write-only
# arguments, so they never appear in Terraform state, in a tfvars file, or as a
# plaintext container environment variable. ECS reads them through the task
# definition's secrets block using the execution role.
#
# Increment secret_version to rotate. Both the database password and SECRET_KEY
# rotate together, in one apply.

ephemeral "random_password" "db" {
  length  = 32
  special = false
}

ephemeral "random_password" "secret_key" {
  length  = 64
  special = false
}

# The backend takes one DATABASE_URL string rather than host/port/user/password
# components, so the whole URL — password included — is composed here and stored
# as a single SecureString.
#
# The prefix must be postgresql://, not postgresql+psycopg://: the backend pins
# psycopg2-binary, and the wrong prefix makes SQLAlchemy fail to find a driver.
resource "aws_ssm_parameter" "database_url" {
  name             = "/${var.name}/${var.environment}/DATABASE_URL"
  description      = "SQLAlchemy URL for the application database"
  type             = "SecureString"
  value_wo         = "postgresql://${local.db_user}:${ephemeral.random_password.db.result}@${local.db_host}:${local.db_port}/${local.db_name}"
  value_wo_version = var.secret_version
}

# Only needed when PostgreSQL runs as a container, which reads POSTGRES_PASSWORD
# rather than a URL.
resource "aws_ssm_parameter" "db_password" {
  count            = var.use_container_database ? 1 : 0
  name             = "/${var.name}/${var.environment}/DB_PASSWORD"
  description      = "Password for the in-task PostgreSQL container"
  type             = "SecureString"
  value_wo         = ephemeral.random_password.db.result
  value_wo_version = var.secret_version
}

resource "aws_ssm_parameter" "secret_key" {
  name             = "/${var.name}/${var.environment}/SECRET_KEY"
  description      = "Application signing key. Replaces the change-me-in-dev default."
  type             = "SecureString"
  value_wo         = ephemeral.random_password.secret_key.result
  value_wo_version = var.secret_version
}
