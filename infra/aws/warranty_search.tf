# Online warranty lookup (CLOUDAPPG5-95).
#
# When a receipt prints no warranty length, the API searches the web through
# Tavily (backend/app/services/warranty_lookup.py). It needs a Tavily API key.
#
# The key is deliberately NOT given to Terraform. Terraform only creates the
# SSM parameter with a placeholder; the real key is put there by hand, so it
# never lands in state, tfvars, git or a plan:
#
#   aws ssm put-parameter --name /<name>/<environment>/TAVILY_API_KEY \
#     --type SecureString --overwrite --value '<key>'
#
# `ignore_changes = [value]` stops later applies from resetting it. ECS reads the
# value when a task starts, so force a new deployment after changing it.
#
# Off by default: warranty_search_provider = "none" creates nothing and the API
# makes no search calls.

variable "warranty_search_provider" {
  description = "Online warranty lookup for receipts that print no warranty: none or tavily. tavily needs the TAVILY_API_KEY parameter filled in after apply."
  type        = string
  default     = "none"
  validation {
    condition     = contains(["none", "tavily"], var.warranty_search_provider)
    error_message = "warranty_search_provider must be none or tavily."
  }
}

locals {
  warranty_search_enabled = var.warranty_search_provider == "tavily"
}

resource "aws_ssm_parameter" "tavily_api_key" {
  count       = local.warranty_search_enabled ? 1 : 0
  name        = "/${var.name}/${var.environment}/TAVILY_API_KEY"
  description = "Tavily search API key for the warranty lookup. Set the real value with aws ssm put-parameter."
  type        = "SecureString"
  value       = "replace-me-with-put-parameter"

  lifecycle {
    ignore_changes = [value]
  }
}
