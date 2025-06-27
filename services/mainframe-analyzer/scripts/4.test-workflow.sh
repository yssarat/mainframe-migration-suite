#!/bin/bash
set -e

# Configuration
REGION="us-east-1"
BUCKET_NAME=""  # Will be set based on account ID and environment
FOLDER_PATH="test-documents"
ENVIRONMENT="dev"  # Options: dev, prod
WAIT_TIME=5  # Seconds to wait between status checks

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region)
      REGION="$2"
      shift 2
      ;;
    --bucket)
      BUCKET_NAME="$2"
      shift 2
      ;;
    --folder)
      FOLDER_PATH="$2"
      shift 2
      ;;
    --env)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --wait)
      WAIT_TIME="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Get AWS account ID if bucket name not provided
if [ -z "$BUCKET_NAME" ]; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  if [ $? -ne 0 ]; then
    echo "Error: Failed to get AWS account ID. Make sure you're authenticated with AWS CLI."
    exit 1
  fi
  
  # Set S3 bucket name based on environment and account ID
  if [ "$ENVIRONMENT" == "prod" ]; then
    BUCKET_NAME="mainframe-transform-prod-${ACCOUNT_ID}"
  else
    BUCKET_NAME="mainframe-transform-dev-${ACCOUNT_ID}"
  fi
fi

echo "Testing Mainframe Transform Workflow:"
echo "  Region: $REGION"
echo "  Bucket: $BUCKET_NAME"
echo "  Folder: $FOLDER_PATH"
echo "  Environment: $ENVIRONMENT"
echo ""

# Check if the test folder exists in S3
if ! aws s3 ls "s3://$BUCKET_NAME/$FOLDER_PATH/" --region "$REGION" &>/dev/null; then
  echo "Error: Test folder not found in S3. Please upload test documents to s3://$BUCKET_NAME/$FOLDER_PATH/"
  exit 1
fi

# Invoke the initial Lambda function
echo "Invoking initial Lambda function to start the workflow..."
RESPONSE=$(aws lambda invoke \
  --function-name mainframe-transform-initial \
  --payload "{\"bucket_name\":\"$BUCKET_NAME\",\"folder_path\":\"$FOLDER_PATH\"}" \
  --cli-binary-format raw-in-base64-out \
  --region "$REGION" \
  /dev/stdout)

# Extract job ID from the response
JOB_ID=$(echo $RESPONSE | jq -r '.body' | jq -r '.job_id')

if [ -z "$JOB_ID" ] || [ "$JOB_ID" == "null" ]; then
  echo "Error: Failed to get job ID from response"
  echo "Response: $RESPONSE"
  exit 1
fi

echo "Job started with ID: $JOB_ID"
echo "Checking job status..."

# Check job status until completion or failure
STATUS="STARTED"
PROGRESS=0
OUTPUT_PATH=""

while [ "$STATUS" != "COMPLETED" ] && [ "$STATUS" != "ERROR" ]; do
  sleep $WAIT_TIME
  
  STATUS_RESPONSE=$(aws lambda invoke \
    --function-name mainframe-transform-status \
    --payload "{\"job_id\":\"$JOB_ID\"}" \
    --cli-binary-format raw-in-base64-out \
    --region "$REGION" \
    /dev/stdout)
  
  STATUS=$(echo $STATUS_RESPONSE | jq -r '.body' | jq -r '.status')
  PROGRESS=$(echo $STATUS_RESPONSE | jq -r '.body' | jq -r '.progress_percentage')
  
  # Check if output path is available
  OUTPUT_PATH=$(echo $STATUS_RESPONSE | jq -r '.body' | jq -r '.output_path')
  if [ "$OUTPUT_PATH" == "null" ]; then
    OUTPUT_PATH=""
  fi
  
  # Check for error
  ERROR=$(echo $STATUS_RESPONSE | jq -r '.body' | jq -r '.message')
  if [[ "$ERROR" == *"failed"* ]]; then
    echo "Error: $ERROR"
  fi
  
  echo "Status: $STATUS, Progress: $PROGRESS%"
  
  # Get file processing information if available
  TOTAL_FILES=$(echo $STATUS_RESPONSE | jq -r '.body' | jq -r '.total_files')
  PROCESSED_FILES=$(echo $STATUS_RESPONSE | jq -r '.body' | jq -r '.processed_files')
  
  if [ "$TOTAL_FILES" != "null" ] && [ "$PROCESSED_FILES" != "null" ]; then
    echo "  Files: $PROCESSED_FILES/$TOTAL_FILES processed"
  fi
done

if [ "$STATUS" == "COMPLETED" ]; then
  echo "Job completed successfully!"
  
  if [ -n "$OUTPUT_PATH" ]; then
    echo "Analysis results available at: $OUTPUT_PATH"
    
    # List the output files
    echo "Output files:"
    aws s3 ls "$OUTPUT_PATH" --recursive --region "$REGION"
    
    # Download a sample result file
    RESULT_FILE="raw_analysis_result.txt"
    LOCAL_RESULT_PATH="analysis-result-$JOB_ID.txt"
    
    # Extract bucket and key from S3 URI
    OUTPUT_BUCKET=$(echo $OUTPUT_PATH | sed -e 's/s3:\/\///' | cut -d'/' -f1)
    OUTPUT_KEY=$(echo $OUTPUT_PATH | sed -e "s/s3:\/\/$OUTPUT_BUCKET\///" | sed -e 's/\/$//')
    
    echo "Downloading analysis result to $LOCAL_RESULT_PATH..."
    aws s3 cp "$OUTPUT_PATH$RESULT_FILE" "$LOCAL_RESULT_PATH" --region "$REGION" || \
    aws s3 cp "s3://$OUTPUT_BUCKET/$OUTPUT_KEY/$RESULT_FILE" "$LOCAL_RESULT_PATH" --region "$REGION" || \
    echo "Could not download result file. Check the S3 path manually."
    
    if [ -f "$LOCAL_RESULT_PATH" ]; then
      echo "Analysis result downloaded successfully"
    fi
  else
    echo "Output path not available"
  fi
else
  echo "Job failed"
  exit 1
fi
