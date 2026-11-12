# Private bucket for receipts and invoices (CLOUDAPPG5-95).
#
# The browser PUTs straight to this bucket with a presigned URL and views
# objects with a presigned GET (docs/architecture.md, Decision 3), so nothing in
# it is ever public. The task role already grants s3:Get/Put/Delete on
# var.document_bucket_name (iam.tf); this file is what creates the bucket that
# name refers to.

variable "extra_cors_origins" {
  description = "Extra browser origins allowed to PUT/GET the bucket, e.g. http://localhost:3000 for local development against the real bucket. The deployed ALB origin is always included."
  type        = list(string)
  default     = []
}

variable "bucket_force_destroy" {
  description = "Let `terraform destroy` delete the bucket even when it holds receipts. Leave false for a real deployment."
  type        = bool
  default     = false
}

resource "aws_s3_bucket" "documents" {
  bucket        = var.document_bucket_name
  force_destroy = var.bucket_force_destroy
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    object_ownership = "BucketOwnerEnforced" # disables ACLs entirely
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # S3-managed keys: no KMS charge
    }
  }
}

# The presigned PUT is issued for the page's own origin, so the browser needs
# CORS to allow it. Content-Type is signed into the URL, hence the header list.
resource "aws_s3_bucket_cors_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  cors_rule {
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = concat([local.app_url], var.extra_cors_origins)
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Refuse any request that is not over TLS.
data "aws_iam_policy_document" "documents_tls_only" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.documents.arn, "${aws_s3_bucket.documents.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "documents" {
  bucket = aws_s3_bucket.documents.id
  policy = data.aws_iam_policy_document.documents_tls_only.json

  depends_on = [aws_s3_bucket_public_access_block.documents]
}

# A presigned upload that never finished leaves invisible, billable parts.
resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}
