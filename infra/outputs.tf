output "api_endpoint" {
  description = "HTTP API base URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "check_url" {
  description = "GET /check — version poll"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/check"
}

output "result_url" {
  description = "POST /result — telemetry"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/result"
}

output "token_url" {
  description = "Cognito client_credentials token endpoint"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com/oauth2/token"
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "install_clients" {
  description = "Demo install Cognito credentials (sub = client_id)"
  sensitive   = true
  value = {
    for key, client in aws_cognito_user_pool_client.install :
    key => {
      client_id     = client.id
      client_secret = client.client_secret
    }
  }
}

output "pins_table" {
  value = aws_dynamodb_table.pins.name
}

output "releases_table" {
  value = aws_dynamodb_table.releases.name
}

output "results_table" {
  value = aws_dynamodb_table.results.name
}

output "releases_bucket" {
  value = aws_s3_bucket.releases.bucket
}

output "oauth_scopes" {
  value = {
    check     = "${aws_cognito_resource_server.api.identifier}/check"
    telemetry = "${aws_cognito_resource_server.api.identifier}/telemetry"
  }
}
