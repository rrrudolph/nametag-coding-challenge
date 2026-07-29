# Machine clients (installs) authenticate via client_credentials.
# Each install gets its own app client so Cognito `sub` == that client id.

resource "aws_cognito_user_pool" "main" {
  name = "${local.name_prefix}-pool"

  admin_create_user_config {
    allow_admin_create_user_only = true
  }
}

resource "aws_cognito_resource_server" "api" {
  identifier   = "update-api"
  name         = "update-api"
  user_pool_id = aws_cognito_user_pool.main.id

  scope {
    scope_name        = "check"
    scope_description = "Poll for version updates and download URLs"
  }

  scope {
    scope_name        = "telemetry"
    scope_description = "Report update success/failure"
  }
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = local.name_prefix
  user_pool_id = aws_cognito_user_pool.main.id
}

# Two demo installs so we can pin one without affecting the other.
resource "aws_cognito_user_pool_client" "install" {
  for_each = toset(["a", "b"])

  name         = "${local.name_prefix}-install-${each.key}"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes = [
    "${aws_cognito_resource_server.api.identifier}/check",
    "${aws_cognito_resource_server.api.identifier}/telemetry",
  ]
  supported_identity_providers = ["COGNITO"]
  explicit_auth_flows          = []

  depends_on = [aws_cognito_resource_server.api]
}
