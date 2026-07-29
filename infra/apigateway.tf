resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.main.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito"

  jwt_configuration {
    audience = [for c in aws_cognito_user_pool_client.install : c.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

resource "aws_apigatewayv2_integration" "update_check" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.update_check.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "telemetry" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.telemetry.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "check" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /check"
  target             = "integrations/${aws_apigatewayv2_integration.update_check.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_scopes = [
    "${aws_cognito_resource_server.api.identifier}/check",
  ]
}

resource "aws_apigatewayv2_route" "result" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /result"
  target             = "integrations/${aws_apigatewayv2_integration.telemetry.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
  authorization_scopes = [
    "${aws_cognito_resource_server.api.identifier}/telemetry",
  ]
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "update_check" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.update_check.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "telemetry" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telemetry.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
