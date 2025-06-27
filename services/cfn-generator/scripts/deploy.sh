#!/bin/bash

# Deploy script for Asynchronous CloudFormation Generator
# This script deploys the CloudFormation templates and Lambda functions

set -e

# Default values
ENVIRONMENT="dev"
REGION=$(aws configure get region)
STACK_NAME="cfn-generator"
PROFILE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --env)
      ENVIRONMENT="$2"
      shift
      shift
      ;;
    --region)
      REGION="$2"
      shift
      shift
      ;;
    --stack-name)
      STACK_NAME="$2"
      shift
      shift
      ;;
    --profile)
      PROFILE="$2"
      shift
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Set AWS profile option if provided
PROFILE_OPTION=""
if [ -n "$PROFILE" ]; then
  PROFILE_OPTION="--profile $PROFILE"
fi

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text $PROFILE_OPTION)
if [ $? -ne 0 ]; then
  echo "Failed to get AWS account ID. Make sure AWS CLI is configured correctly."
  exit 1
fi

# Set full stack name with environment
FULL_STACK_NAME="${STACK_NAME}-${ENVIRONMENT}"

# Set S3 bucket name for Lambda code
S3_BUCKET="cfn-generator-${ENVIRONMENT}-${ACCOUNT_ID}-${REGION}"

echo "Deploying Asynchronous CloudFormation Generator"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Stack name: $FULL_STACK_NAME"
echo "S3 bucket: $S3_BUCKET"

# Create a temporary bucket for Lambda code
TEMP_BUCKET="cfn-generator-temp-${ENVIRONMENT}-${ACCOUNT_ID}-${REGION}"

# Check if temporary S3 bucket exists, create if not
if ! aws s3api head-bucket --bucket "$TEMP_BUCKET" $PROFILE_OPTION 2>/dev/null; then
  echo "Creating temporary S3 bucket: $TEMP_BUCKET"
  aws s3 mb "s3://$TEMP_BUCKET" --region "$REGION" $PROFILE_OPTION
  
  # Wait for bucket to be available
  echo "Waiting for S3 bucket to be available..."
  sleep 5
fi

# Create Lambda deployment packages
echo "Creating Lambda deployment packages..."
mkdir -p dist

# Initial Lambda
echo "Packaging Initial Lambda..."
cd src
zip -r ../dist/initial-lambda.zip initial-lambda/lambda_function.py
cd ..

# Status Lambda
echo "Packaging Status Lambda..."
cd src
zip -r ../dist/status-lambda.zip status-lambda/lambda_function.py
cd ..

# Generator Lambda
echo "Packaging Generator Lambda..."
cd src
zip -r ../dist/generator-lambda.zip generator/lambda_function.py
cd ..

# Completion Lambda
echo "Packaging Completion Lambda..."
cd src
zip -r ../dist/completion-lambda.zip completion/lambda_function.py
cd ..

# Validation Lambda
echo "Packaging Validation Lambda..."
cd src
zip -r ../dist/validation-lambda.zip validation-lambda/lambda_function.py
cd ..

# Upload Lambda packages to S3
echo "Uploading Lambda packages to S3..."
aws s3 cp dist/initial-lambda.zip "s3://$TEMP_BUCKET/lambda/initial-lambda.zip" $PROFILE_OPTION
aws s3 cp dist/status-lambda.zip "s3://$TEMP_BUCKET/lambda/status-lambda.zip" $PROFILE_OPTION
aws s3 cp dist/generator-lambda.zip "s3://$TEMP_BUCKET/lambda/generator-lambda.zip" $PROFILE_OPTION
aws s3 cp dist/completion-lambda.zip "s3://$TEMP_BUCKET/lambda/completion-lambda.zip" $PROFILE_OPTION
aws s3 cp dist/validation-lambda.zip "s3://$TEMP_BUCKET/lambda/validation-lambda.zip" $PROFILE_OPTION

# Deploy main CloudFormation stack
echo "Deploying main CloudFormation stack..."
aws cloudformation deploy \
  --template-file cloudformation/main.yaml \
  --stack-name "$FULL_STACK_NAME" \
  --parameter-overrides \
    Environment="$ENVIRONMENT" \
    LambdaCodeBucket="$TEMP_BUCKET" \
    LambdaTimeout=600 \
    LambdaMemory=1024 \
    BedrockModelId="arn:aws:bedrock:${REGION}:${ACCOUNT_ID}:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0" \
    ArchiveRetentionDays=30 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  $PROFILE_OPTION

# Get outputs from main stack
echo "Getting outputs from main stack..."
INITIAL_LAMBDA_ARN=$(aws cloudformation describe-stacks --stack-name "$FULL_STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='InitialLambdaArn'].OutputValue" --output text --region "$REGION" $PROFILE_OPTION)
STATUS_LAMBDA_ARN=$(aws cloudformation describe-stacks --stack-name "$FULL_STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='StatusLambdaArn'].OutputValue" --output text --region "$REGION" $PROFILE_OPTION)

# Deploy Bedrock agent stack
echo "Deploying Bedrock agent stack..."
# Skip Bedrock agent deployment for now due to resource type issues
echo "Skipping Bedrock agent deployment due to resource type issues"

# aws cloudformation deploy \
#   --template-file cloudformation/bedrock-agent.yaml \
#   --stack-name "${FULL_STACK_NAME}-agent" \
#   --parameter-overrides \
#     Environment="$ENVIRONMENT" \
#     InitialLambdaArn="$INITIAL_LAMBDA_ARN" \
#     StatusLambdaArn="$STATUS_LAMBDA_ARN" \
#   --capabilities CAPABILITY_IAM \
#   --region "$REGION" \
#   $PROFILE_OPTION

echo "Deployment completed successfully!"
echo "Main stack: $FULL_STACK_NAME"
echo "Agent stack: ${FULL_STACK_NAME}-agent"
