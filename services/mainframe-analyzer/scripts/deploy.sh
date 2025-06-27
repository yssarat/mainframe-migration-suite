#!/bin/bash
set -e

# Configuration
STACK_NAME="mainframe-transform"
REGION="us-east-1"
ENVIRONMENT="dev"  # Options: dev, prod
S3_BUCKET=""  # Will be set based on account ID

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

echo "Deploying Mainframe Transform Project to:"
echo "  Stack Name: $STACK_NAME"
echo "  Region: $REGION"
echo "  Environment: $ENVIRONMENT"
echo "  S3 Bucket: $S3_BUCKET"
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
  if [ -d "$function_dir" ]; then
    function_name=$(basename "$function_dir")
    package_path=$(package_lambda "$function_dir")
    # echo "Uploading $function_name package to S3..."
    # aws s3 cp "$package_path" "s3://$S3_BUCKET/lambda/${function_name}.zip" --region "$REGION"
  fi
done

echo "Uploading $function_name package to S3..."
aws s3 cp "$TEMP_DIR" "s3://$S3_BUCKET/lambda/" --region "$REGION" --recursive

## Creating and Uploading lambda layer
echo "Creating and Uploading lambda layers"
mkdir -p python/lib/python3.9/site-packages

# Install packages
pip install pypdf -t python/lib/python3.9/site-packages
pip install docx -t python/lib/python3.9/site-packages

# Zip the layer
zip -r pypdfdocxlayer.zip python/

# Copy layer to S3
echo "Uploading layer to S3..."
aws s3 cp pypdfdocxlayer.zip "s3://$S3_BUCKET/layer/" --region "$REGION"


## Deploy CloudFormation stack
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
  --template-file "$PROJECT_DIR/../cloudformation/cloudformation.yaml" \
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
