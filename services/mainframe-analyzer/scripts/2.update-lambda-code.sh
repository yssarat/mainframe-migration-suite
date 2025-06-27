#!/bin/bash
set -e

# Configuration
REGION="us-east-1"
ENVIRONMENT="dev"  # Options: dev, prod
S3_BUCKET=""  # Will be set based on account ID
FUNCTION_NAME=""  # Optional: specific function to update

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region)
      REGION="$2"
      shift 2
      ;;
    --env)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --function)
      FUNCTION_NAME="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ]; then
  echo "Error: Failed to get AWS account ID. Make sure you're authenticated with AWS CLI."
  exit 1
fi

# Set S3 bucket name based on environment and account ID
if [ "$ENVIRONMENT" == "prod" ]; then
  S3_BUCKET="mainframe-transform-prod-${ACCOUNT_ID}"
else
  S3_BUCKET="mainframe-transform-dev-${ACCOUNT_ID}"
fi

echo "Updating Lambda code for Mainframe Transform Project:"
echo "  Region: $REGION"
echo "  Environment: $ENVIRONMENT"
echo "  S3 Bucket: $S3_BUCKET"
if [ -n "$FUNCTION_NAME" ]; then
  echo "  Function: $FUNCTION_NAME"
fi
echo ""

# Create a temporary directory for packaging
TEMP_DIR=$(mktemp -d)
echo "Created temporary directory: $TEMP_DIR"

# Function to package Lambda functions
package_lambda() {
  local function_dir=$1
  local function_name=$(basename $function_dir)
  local package_path="$TEMP_DIR/${function_name}.zip"
  
  echo "Packaging $function_name Lambda function..."
  
  # Create the ZIP package directly from the lambda function directory
  cd "$function_dir"
  zip -r "$package_path" .
  
  echo "Successfully packaged $function_name"
  
  # Return the package path
  echo "$package_path"
}

# Package and upload Lambda functions
echo "Packaging Lambda functions..."
PROJECT_DIR=$(pwd)
SRC_DIR="$PROJECT_DIR/../src"

if [ -n "$FUNCTION_NAME" ]; then
  # Update a specific function
  function_dir="$SRC_DIR/$FUNCTION_NAME-lambda"
  if [ ! -d "$function_dir" ]; then
    echo "Error: Function directory not found: $function_dir"
    exit 1
  fi
  
  package_path=$(package_lambda "$function_dir")
  
  echo "Uploading $FUNCTION_NAME-lambda package to S3..."
  aws s3 cp "$package_path" "s3://$S3_BUCKET/lambda/${FUNCTION_NAME}-lambda.zip" --region "$REGION"
  
  echo "Updating Lambda function code..."
  aws lambda update-function-code \
    --function-name "mainframe-transform-${FUNCTION_NAME}" \
    --s3-bucket "$S3_BUCKET" \
    --s3-key "lambda/${FUNCTION_NAME}-lambda.zip" \
    --region "$REGION"
else
  # Update all functions
  for function_dir in "$SRC_DIR"/*; do
    if [ -d "$function_dir" ]; then
      function_name=$(basename "$function_dir")
      
      # Extract the base name without -lambda suffix
      base_name=${function_name%-lambda}
      
      package_path=$(package_lambda "$function_dir")
      
      echo "Uploading $function_name package to S3..."
      aws s3 cp "$package_path" "s3://$S3_BUCKET/lambda/${function_name}.zip" --region "$REGION"
      
      echo "Updating Lambda function code for mainframe-transform-$base_name..."
      aws lambda update-function-code \
        --function-name "mainframe-transform-$base_name" \
        --s3-bucket "$S3_BUCKET" \
        --s3-key "lambda/${function_name}.zip" \
        --region "$REGION"
    fi
  done
fi

# Clean up
rm -rf "$TEMP_DIR"
echo "Lambda code update completed successfully!"
