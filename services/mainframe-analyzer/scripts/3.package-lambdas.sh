#!/bin/bash
set -e

# Configuration
REGION="us-east-1"
ENVIRONMENT="dev"  # Options: dev, prod
S3_BUCKET=""  # Will be set based on account ID
OUTPUT_DIR="./dist"

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
    --output)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --skip-s3)
      SKIP_S3=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Get AWS account ID if not skipping S3
if [ -z "$SKIP_S3" ]; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  if [ $? -ne 0 ]; then
    echo "Error: Failed to get AWS account ID. Make sure you're authenticated with AWS CLI."
    echo "If you don't need S3 upload, use --skip-s3 flag."
    exit 1
  fi

  # Set S3 bucket name based on environment and account ID
  if [ "$ENVIRONMENT" == "prod" ]; then
    S3_BUCKET="mainframe-transform-prod-${ACCOUNT_ID}"
  else
    S3_BUCKET="mainframe-transform-dev-${ACCOUNT_ID}"
  fi
fi

# Get the project root directory (one level up from scripts)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Convert OUTPUT_DIR to absolute path if it's relative
if [[ ! "$OUTPUT_DIR" = /* ]]; then
  OUTPUT_DIR="$PROJECT_DIR/$OUTPUT_DIR"
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "Packaging Lambda functions for Mainframe Transform Project:"
echo "  Region: $REGION"
echo "  Environment: $ENVIRONMENT"
if [ -z "$SKIP_S3" ]; then
  echo "  S3 Bucket: $S3_BUCKET"
fi
echo "  Output Directory: $OUTPUT_DIR"
echo ""

# Function to package Lambda functions
package_lambda() {
  local function_dir=$1
  local function_name=$(basename "$function_dir")
  local package_path="$OUTPUT_DIR/${function_name}.zip"
  local current_dir=$(pwd)
  
  echo "Packaging $function_name Lambda function..."
  echo "  Source directory: $function_dir"
  echo "  Output path: $package_path"
  
  # Create the ZIP package directly from the lambda function directory
  cd "$function_dir"
  zip -r "$package_path" .
  local zip_status=$?
  
  # Return to the original directory
  cd "$current_dir"
  
  if [ $zip_status -eq 0 ]; then
    echo "Successfully packaged $function_name to $package_path"
    return 0
  else
    echo "Failed to package $function_name"
    return 1
  fi
}

SRC_DIR="$PROJECT_DIR/src"

echo "Project directory: $PROJECT_DIR"
echo "Source directory: $SRC_DIR"
echo "Packaging Lambda functions..."

# Package each Lambda function
for function_dir in "$SRC_DIR"/*; do
  if [ -d "$function_dir" ]; then
    function_name=$(basename "$function_dir")
    package_lambda "$function_dir"
    
    # Check if packaging was successful
    if [ $? -eq 0 ]; then
      # Upload to S3 if requested
      if [ -z "$SKIP_S3" ]; then
        echo "Uploading $function_name package to S3..."
        aws s3 cp "$OUTPUT_DIR/${function_name}.zip" "s3://$S3_BUCKET/lambda/${function_name}.zip" --region "$REGION"
      fi
    else
      echo "Failed to package $function_name"
    fi
  fi
done

echo "Lambda packaging completed successfully!"
echo "Lambda packages are available in $OUTPUT_DIR"
