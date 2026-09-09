terraform {
  required_version = ">= 1.8.0"
  required_providers { aws = { source = "hashicorp/aws" } }
}
provider "aws" {
  region = var.aws_region
  default_tags { tags = { Project = "black-outcomes-intelligence" Environment = var.environment } }
}
resource "aws_s3_bucket" "lake" { bucket_prefix = "black-outcomes-intelligence-${var.environment}-" }
resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_public_access_block" "lake" {
  bucket = aws_s3_bucket.lake.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_glue_catalog_database" "analytics" { name = "black_outcomes_${var.environment}" }
