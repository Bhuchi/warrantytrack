# Cognito authenticates. It does not decide what anyone is allowed to do —
# PostgreSQL owns permissions. See docs/architecture.md, Decision 2.
#
# No Cognito Groups: groups are global to the user pool, so a user who is an
# admin of one organization and an employee of another cannot be expressed.
# Roles live in the memberships table instead.

resource "aws_cognito_user_pool" "main" {
  name                     = "${var.name}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

# Public browser client, so no secret. The frontend inlines this client ID at
# build time via NEXT_PUBLIC_COGNITO_CLIENT_ID, which is why Cognito is applied
# before the web image is built — see DEPLOYMENT.md.
resource "aws_cognito_user_pool_client" "web" {
  name            = "${var.name}-web"
  user_pool_id    = aws_cognito_user_pool.main.id
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  prevent_user_existence_errors        = "ENABLED"
  allowed_oauth_flows_user_pool_client = false
}
