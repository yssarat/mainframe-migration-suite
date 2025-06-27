#!/bin/bash
set -e

# First, change to the script's directory
cd "$(dirname "$0")"

# Configuration
STACK_NAME="mainframe-transform"
REGION="us-east-1"
ENVIRONMENT="dev"  # Options: dev, prod
S3_BUCKET=""  # Will be set based on account ID
TEMPLATE_PATH="../cloudformation/main.yaml"  # Relative to scripts directory

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --env)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --template)
      TEMPLATE_PATH="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--stack-name NAME] [--region REGION] [--env ENV] [--template PATH]"
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

echo "Deploying Mainframe Transform Project to:"
echo "  Stack Name: $STACK_NAME"
echo "  Region: $REGION"
echo "  Environment: $ENVIRONMENT"
echo "  S3 Bucket: $S3_BUCKET"
echo ""

# Create a temporary directory for packaging
TEMP_DIR=$(mktemp -d)
echo "Created temporary directory: $TEMP_DIR"

# Check if the S3 bucket exists, create it if it doesn't
echo "Checking if S3 bucket exists..."
if ! aws s3api head-bucket --bucket "$S3_BUCKET" --region "$REGION" 2>/dev/null; then
  echo "Creating S3 bucket: $S3_BUCKET"
  
  # Create bucket with appropriate region syntax
  if [ "$REGION" == "us-east-1" ]; then
    aws s3api create-bucket --bucket "$S3_BUCKET" --region "$REGION"
  else
    aws s3api create-bucket --bucket "$S3_BUCKET" --region "$REGION" --create-bucket-configuration LocationConstraint="$REGION"
  fi
  
  # Enable versioning
  aws s3api put-bucket-versioning --bucket "$S3_BUCKET" --versioning-configuration Status=Enabled --region "$REGION"
  
  echo "S3 bucket created successfully"
else
  echo "S3 bucket already exists"
fi

# Package and upload Lambda functions
echo "Packaging Lambda functions..."
PROJECT_DIR=$(pwd)
SRC_DIR="$PROJECT_DIR/../src"

for function_dir in "$SRC_DIR"/*; do
  if [ -d "$function_dir" ] && [ "$(basename "$function_dir")" != "." ] && [ "$(basename "$function_dir")" != ".." ]; then
    function_name=$(basename "$function_dir")
    
    # Skip if not a lambda directory (e.g., README.md)
    if [[ ! "$function_name" =~ .*lambda$ ]]; then
      continue
    fi
    
    echo "Processing $function_name..."
    
    # Create zip file directly
    zip_file="$TEMP_DIR/${function_name}.zip"
    (cd "$function_dir" && zip -r "$zip_file" . -x "*.DS_Store" "*.pyc" "__pycache__/*")
    
    if [ -f "$zip_file" ]; then
      echo "Uploading $function_name package to S3..."
      aws s3 cp "$zip_file" "s3://$S3_BUCKET/lambda/${function_name}.zip" --region "$REGION"
    else
      echo "Error: Failed to create zip file for $function_name"
      exit 1
    fi
  fi
done

# Deploy CloudFormation stack
echo "Deploying CloudFormation stack..."

# Read parameters from JSON file and convert to key=value format
PARAMS_FILE="$PROJECT_DIR/../cloudformation/parameters/${ENVIRONMENT}.json"
PARAMS=""

# Check if parameters file exists
if [ -f "$PARAMS_FILE" ]; then
  # Check if jq is installed
  if command -v jq &> /dev/null; then
    # Use jq to extract parameters
    PARAMS=$(jq -r '.[] | .ParameterKey + "=" + .ParameterValue' "$PARAMS_FILE" | tr '\n' ' ')
  else
    echo "Warning: jq is not installed. Using file reference for parameters."
    PARAMS="file://$PARAMS_FILE"
  fi
  
  # Replace ${AWS::AccountId} with actual account ID in parameters
  PARAMS=${PARAMS//\$\{AWS::AccountId\}/$ACCOUNT_ID}
else
  echo "Parameters file not found. Using default parameters."
  PARAMS="Environment=$ENVIRONMENT S3BucketName=$S3_BUCKET"
fi

aws cloudformation deploy \
  --template-file "$TEMPLATE_PATH" \
  --stack-name "$STACK_NAME" \
  --parameter-overrides $PARAMS \
  --capabilities CAPABILITY_IAM \
  --region "$REGION"

# Clean up
rm -rf "$TEMP_DIR"
echo "Deployment completed successfully!"

# Display stack outputs
echo "Stack outputs:"
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs" --output table --region "$REGION"
