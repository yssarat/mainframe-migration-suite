# Mainframe Modernization Lambda Functions

This directory contains the Lambda functions used in the Mainframe Modernization project. Each function plays a specific role in the serverless architecture for analyzing mainframe documentation.

## Lambda Functions

### 1. Initial Lambda (`initial-lambda/`)

Entry point for the workflow that:
- Validates input parameters (S3 bucket and folder path)
- Lists files in the specified S3 location
- Creates a job record in DynamoDB
- Starts the Step Functions workflow

### 2. Process File Lambda (`process-file-lambda/`)

Processes individual files by:
- Extracting text from various document formats (PDF, DOCX, TXT)
- Uploading extracted text to S3
- Updating job progress in DynamoDB

### 3. Aggregate Lambda (`aggregate-lambda/`)

Combines processed file contents by:
- Merging extracted text from all processed files
- Preparing the full prompt for analysis
- Updating job status in DynamoDB

### 4. Analysis Lambda (`analysis-lambda/`)

Performs AI-powered analysis by:
- Sending the aggregated content to Amazon Bedrock
- Parsing the response by AWS service type
- Saving results to S3
- Updating job status to completed

### 5. Status Lambda (`status-lambda/`)

Provides job status information by:
- Retrieving job details from DynamoDB
- Checking execution details from Step Functions
- Listing output files from S3
- Calculating progress percentage

## Workflow

The Lambda functions work together in a Step Functions workflow:

1. Initial Lambda starts the process and creates a job record
2. Process File Lambda runs in parallel for each file (using Step Functions Map state)
3. Aggregate Lambda combines the extracted text from all files
4. Analysis Lambda sends the combined text to Bedrock for analysis
5. Status Lambda can be called at any time to check job progress

## Environment Variables

The Lambda functions use the following environment variables:

- `JOBS_TABLE_NAME`: DynamoDB table name for job tracking (default: MainframeAnalyzerJobs)
- `STATE_MACHINE_ARN`: ARN of the Step Functions state machine
- `MAX_FILES`: Maximum number of files to process (default: 100)
- `MAX_COMBINED_CHARS`: Maximum combined character count for analysis (default: 100000)
- `PARAMETER_STORE_PREFIX`: Prefix for parameters in Parameter Store (default: /mainframe-analyzer/)
- `BEDROCK_MODEL_ID`: Bedrock model ID to use (default: anthropic.claude-3-sonnet-20240229-v1:0)
