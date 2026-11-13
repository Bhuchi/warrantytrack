variable "aws_region" {
  description = "Deployment region. Singapore per docs/architecture.md."
  type        = string
  default     = "ap-southeast-1"
}

variable "name" {
  description = "Lowercase prefix for every resource name."
  type        = string
  default     = "warrantytrack"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,24}$", var.name))
    error_message = "name must be 3-25 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "environment" {
  description = "Value for the backend's ENVIRONMENT setting, and the Environment tag."
  type        = string
  default     = "production"
}

# ---------------------------------------------------------------------------
# The private documents bucket and CORS rules are created by storage.tf.
# Choose a globally unique name before applying the full stack.
# ---------------------------------------------------------------------------

variable "document_bucket_name" {
  description = "Globally unique name for the private receipts and invoices bucket created by this stack."
  type        = string
}

variable "ses_sender_email" {
  description = "SES sender address. This stack requests the identity; the inbox owner must complete verification."
  type        = string
  validation {
    condition     = can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.ses_sender_email))
    error_message = "Provide a valid email address."
  }
}

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

variable "image_tag" {
  description = "Tag pushed to both ECR repositories. Keep in sync after every deploy."
  type        = string
  default     = "bootstrap"
}

variable "desired_count" {
  description = "Running tasks. One normally; two only for the demo (docs/architecture.md cost discipline)."
  type        = number
  default     = 1
  validation {
    condition     = contains([0, 1, 2], var.desired_count)
    error_message = "desired_count must be 0, 1 or 2."
  }
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB. Raise to 2048 when use_container_database is true."
  type        = number
  default     = 1024
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_multi_az" {
  description = "Multi-AZ is the production answer and is documented as such in the report, but it doubles the database bill. Single-AZ for the semester."
  type        = bool
  default     = false
}

variable "use_container_database" {
  description = "Run PostgreSQL as a container inside the ECS task instead of RDS, for lab accounts that deny rds:CreateDBInstance. Data is ephemeral and lost whenever the task restarts. Never true for a real deployment."
  type        = bool
  default     = false
}

variable "secret_version" {
  description = "Increment to rotate the generated database password and SECRET_KEY together. Rotating writes new values to RDS and SSM in one apply."
  type        = number
  default     = 1
  validation {
    condition     = var.secret_version >= 1 && floor(var.secret_version) == var.secret_version
    error_message = "secret_version must be a positive integer."
  }
}

# ---------------------------------------------------------------------------
# IAM and cost
# ---------------------------------------------------------------------------

variable "create_iam_roles" {
  description = "Create scoped execution and task roles. Set false in an AWS Academy Learner Lab, which denies IAM role creation and provides LabRole instead."
  type        = bool
  default     = true
}

variable "existing_role_name" {
  description = "Role used for both execution and task role when create_iam_roles is false."
  type        = string
  default     = "LabRole"
}

variable "budget_limit_usd" {
  description = "Monthly AWS Budgets alert threshold. The project budget is THB 4,000 for the semester; infra/README.md says set this before creating any resource."
  type        = number
  default     = 110
}

variable "budget_alert_email" {
  description = "Address that receives the budget alert."
  type        = string
}
