data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "update_check" {
  name               = "${local.name_prefix}-update-check"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role" "telemetry" {
  name               = "${local.name_prefix}-telemetry"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "update_check_logs" {
  role       = aws_iam_role.update_check.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "telemetry_logs" {
  role       = aws_iam_role.telemetry.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "update_check" {
  statement {
    sid = "PinAndReleaseReads"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
    ]
    resources = [
      aws_dynamodb_table.pins.arn,
      aws_dynamodb_table.releases.arn,
    ]
  }

  statement {
    sid = "PresignDownloads"
    actions = [
      "s3:GetObject",
    ]
    resources = ["${aws_s3_bucket.releases.arn}/*"]
  }
}

resource "aws_iam_role_policy" "update_check" {
  name   = "update-check"
  role   = aws_iam_role.update_check.id
  policy = data.aws_iam_policy_document.update_check.json
}

data "aws_iam_policy_document" "telemetry" {
  statement {
    sid = "WriteResults"
    actions = [
      "dynamodb:PutItem",
    ]
    resources = [aws_dynamodb_table.results.arn]
  }
}

resource "aws_iam_role_policy" "telemetry" {
  name   = "telemetry"
  role   = aws_iam_role.telemetry.id
  policy = data.aws_iam_policy_document.telemetry.json
}
