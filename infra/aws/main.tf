data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  db_name = "warrantytrack"
  db_user = "warrantytrack"

  # The container database shares the task's network namespace, so the API
  # reaches it on loopback. RDS supplies a real endpoint instead.
  db_host = var.use_container_database ? "127.0.0.1" : one(aws_db_instance.main[*].address)
  db_port = var.use_container_database ? 5432 : one(aws_db_instance.main[*].port)

  app_url = "http://${aws_lb.main.dns_name}"

  # Matches backend/app/core/config.py exactly. Names that do not match are
  # silently discarded, because Settings is configured extra="ignore".
  #
  # CORS_ORIGINS is typed list[str], and pydantic-settings parses JSON for list
  # fields, so it must be a JSON array string — a bare URL fails at startup.
  #
  # DATABASE_URL and SECRET_KEY are not here: they are injected from SSM
  # SecureStrings through the task definition's secrets block.
  api_environment = [
    { name = "ENVIRONMENT", value = var.environment },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "S3_BUCKET_NAME", value = var.document_bucket_name },
    { name = "COGNITO_USER_POOL_ID", value = aws_cognito_user_pool.main.id },
    { name = "COGNITO_CLIENT_ID", value = aws_cognito_user_pool_client.web.id },
    { name = "SES_SENDER_EMAIL", value = var.ses_sender_email },
    # The defaults are the local/fake backends, which config.py refuses to run
    # with in production. Without these three the API fails at startup.
    { name = "STORAGE_BACKEND", value = "s3" },
    { name = "OCR_BACKEND", value = var.ocr_backend },
    { name = "BEDROCK_MODEL_ID", value = var.bedrock_model_id },
    { name = "BEDROCK_REGION", value = var.bedrock_region },
    { name = "EMAIL_BACKEND", value = "ses" },
    { name = "CORS_ORIGINS", value = jsonencode([local.app_url]) },
    { name = "WARRANTY_SEARCH_PROVIDER", value = var.warranty_search_provider }
  ]

  api_secrets = concat(
    [
      { name = "DATABASE_URL", valueFrom = aws_ssm_parameter.database_url.arn },
      { name = "SECRET_KEY", valueFrom = aws_ssm_parameter.secret_key.arn }
    ],
    local.warranty_search_enabled ? [
      { name = "TAVILY_API_KEY", valueFrom = one(aws_ssm_parameter.tavily_api_key[*].arn) }
    ] : []
  )
}
