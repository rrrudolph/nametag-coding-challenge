# Sparse pin table: one row per active client or platform pin.
# pin_key examples: "client#<cognito-sub>", "platform#linux/amd64"
resource "aws_dynamodb_table" "pins" {
  name         = "${local.name_prefix}-pins"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pin_key"

  attribute {
    name = "pin_key"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}

# Release metadata keyed by (version, platform).
# Also stores well-known items with version = "latest" pointing at current.
resource "aws_dynamodb_table" "releases" {
  name         = "${local.name_prefix}-releases"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "version"
  range_key    = "platform"

  attribute {
    name = "version"
    type = "S"
  }

  attribute {
    name = "platform"
    type = "S"
  }
}

# Telemetry: update success/failure reports from clients.
resource "aws_dynamodb_table" "results" {
  name         = "${local.name_prefix}-results"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "client_id"
  range_key    = "reported_at"

  attribute {
    name = "client_id"
    type = "S"
  }

  attribute {
    name = "reported_at"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}
