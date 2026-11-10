# Amazon SES identities for expiry emails (CLOUDAPPG5-98).
#
# Creating an identity makes SES send a verification email; the link in it must
# be clicked by whoever owns the inbox. Terraform cannot do that step.
#
# A new account is in the SES SANDBOX: it can only send TO verified addresses.
# Leaving the sandbox is a support request made in the console, not a Terraform
# resource. Until then, list every team/demo recipient below.
#
# backend/app/services/email.py uses the SES v1 API (boto3 "ses"), so these are
# v1 identities, matching the ses:SendEmail grant in iam.tf.

variable "ses_verified_recipients" {
  description = "Extra addresses to verify while SES is in sandbox (team members, demo accounts). The sender is verified separately and need not be listed."
  type        = list(string)
  default     = []
}

resource "aws_ses_email_identity" "sender" {
  email = var.ses_sender_email
}

resource "aws_ses_email_identity" "recipient" {
  for_each = toset([for e in var.ses_verified_recipients : lower(e) if lower(e) != lower(var.ses_sender_email)])
  email    = each.value
}
