data "archive_file" "update_check" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/update_check.py"
  output_path = "${path.module}/build/update_check.zip"
}

data "archive_file" "telemetry" {
  type        = "zip"
  source_file = "${path.module}/../lambdas/telemetry.py"
  output_path = "${path.module}/build/telemetry.zip"
}

resource "aws_lambda_function" "update_check" {
  function_name = "${local.name_prefix}-update-check"
  role          = aws_iam_role.update_check.arn
  handler       = "update_check.handler"
  runtime       = "python3.12"
  timeout       = 10
  memory_size   = 128

  filename         = data.archive_file.update_check.output_path
  source_code_hash = data.archive_file.update_check.output_base64sha256

  environment {
    variables = {
      PINS_TABLE     = aws_dynamodb_table.pins.name
      RELEASES_TABLE = aws_dynamodb_table.releases.name
      RELEASES_BUCKET = aws_s3_bucket.releases.bucket
    }
  }
}

resource "aws_lambda_function" "telemetry" {
  function_name = "${local.name_prefix}-telemetry"
  role          = aws_iam_role.telemetry.arn
  handler       = "telemetry.handler"
  runtime       = "python3.12"
  timeout       = 10
  memory_size   = 128

  filename         = data.archive_file.telemetry.output_path
  source_code_hash = data.archive_file.telemetry.output_base64sha256

  environment {
    variables = {
      RESULTS_TABLE = aws_dynamodb_table.results.name
    }
  }
}

resource "aws_cloudwatch_log_group" "update_check" {
  name              = "/aws/lambda/${aws_lambda_function.update_check.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "telemetry" {
  name              = "/aws/lambda/${aws_lambda_function.telemetry.function_name}"
  retention_in_days = 14
}
