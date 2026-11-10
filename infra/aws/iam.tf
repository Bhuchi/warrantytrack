# Two roles when the account allows it:
#   execution role — what ECS itself needs: pull from ECR, write logs, read the
#                    SSM SecureStrings named in the task definition.
#   task role      — what the application code needs: S3, Textract, SES.
#
# An AWS Academy Learner Lab denies IAM role creation and supplies LabRole
# instead. Set create_iam_roles = false there; LabRole is used for both.

data "aws_iam_role" "existing" {
  count = var.create_iam_roles ? 0 : 1
  name  = var.existing_role_name
}

data "aws_iam_policy_document" "ecs_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------------------
# Execution role
# ---------------------------------------------------------------------------

resource "aws_iam_role" "execution" {
  count              = var.create_iam_roles ? 1 : 0
  name               = "${var.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  count      = var.create_iam_roles ? 1 : 0
  role       = aws_iam_role.execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Scoped to this stack's parameters only, not the whole Parameter Store.
resource "aws_iam_role_policy" "execution_secrets" {
  count = var.create_iam_roles ? 1 : 0
  name  = "${var.name}-read-secrets"
  role  = aws_iam_role.execution[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParameters"]
        Resource = compact([
          aws_ssm_parameter.database_url.arn,
          aws_ssm_parameter.secret_key.arn,
          one(aws_ssm_parameter.db_password[*].arn)
        ])
      },
      {
        # SecureStrings are encrypted with the AWS-managed aws/ssm key. The
        # condition keeps this from being a general decrypt grant.
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*"
        Condition = {
          StringEquals = { "kms:ViaService" = "ssm.${var.aws_region}.amazonaws.com" }
        }
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Task role
# ---------------------------------------------------------------------------

resource "aws_iam_role" "task" {
  count              = var.create_iam_roles ? 1 : 0
  name               = "${var.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust.json
}

resource "aws_iam_role_policy" "task" {
  count = var.create_iam_roles ? 1 : 0
  name  = "${var.name}-app-services"
  role  = aws_iam_role.task[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = "arn:aws:s3:::${var.document_bucket_name}"
      },
      {
        # Presigned PUT and GET are generated with these credentials, so the
        # browser never needs AWS access of its own. See architecture Decision 3.
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "arn:aws:s3:::${var.document_bucket_name}/*"
      },
      {
        # AnalyzeExpense for receipts; the Start/Get pair for multi-page PDFs,
        # which must use the asynchronous API.
        Effect = "Allow"
        Action = [
          "textract:AnalyzeExpense",
          "textract:StartExpenseAnalysis",
          "textract:GetExpenseAnalysis",
          "textract:DetectDocumentText"
        ]
        Resource = "*"
      },
      {
        # Claude on Bedrock reads receipts (OCR_BACKEND=bedrock). Resource "*"
        # because a global inference profile fans out to foundation-model ARNs
        # in several regions; tighten once the model ID is final.
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = "*"
        Condition = {
          StringEquals = { "ses:FromAddress" = var.ses_sender_email }
        }
      }
    ]
  })
}

locals {
  execution_role_arn = var.create_iam_roles ? aws_iam_role.execution[0].arn : data.aws_iam_role.existing[0].arn
  task_role_arn      = var.create_iam_roles ? aws_iam_role.task[0].arn : data.aws_iam_role.existing[0].arn
}
