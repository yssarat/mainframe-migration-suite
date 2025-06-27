# Mainframe Transform Project Scripts

This directory contains scripts for deploying and managing the Mainframe Transform Project.

## Scripts Overview

1. **1.deploy.sh**: Deploys the CloudFormation stack for the Mainframe Transform Project.
2. **2.update-lambda-code.sh**: Updates the Lambda function code without redeploying the entire stack.
3. **3.package-lambdas.sh**: Packages Lambda functions and uploads them to S3.
4. **4.test-workflow.sh**: Tests the Mainframe Transform workflow with sample documents.

## Usage Instructions

### 1. Deploy CloudFormation Stack

```bash
./1.deploy.sh --region us-east-1 --env dev --stack-name mainframe-transform
```

Options:
- `--region`: AWS region (default: us-east-1)
- `--env`: Environment (dev or prod, default: dev)
- `--stack-name`: CloudFormation stack name (default: mainframe-transform)

### 2. Update Lambda Code

```bash
./2.update-lambda-code.sh --region us-east-1 --env dev --function initial
```

Options:
- `--region`: AWS region (default: us-east-1)
- `--env`: Environment (dev or prod, default: dev)
- `--function`: Specific Lambda function to update (optional, updates all if not specified)

### 3. Package Lambda Functions

```bash
./3.package-lambdas.sh --region us-east-1 --env dev --output ./dist
```

Options:
- `--region`: AWS region (default: us-east-1)
- `--env`: Environment (dev or prod, default: dev)
- `--output`: Output directory for packaged Lambda functions (default: ./dist)

### 4. Test Workflow

```bash
./4.test-workflow.sh --region us-east-1 --bucket your-bucket --folder your-folder
```

Options:
- `--region`: AWS region (default: us-east-1)
- `--bucket`: S3 bucket name (optional, derived from environment if not specified)
- `--folder`: S3 folder containing test documents (default: test-documents)
- `--env`: Environment (dev or prod, default: dev)
- `--wait`: Wait time in seconds between status checks (default: 5)

## Lambda Functions

The Mainframe Transform Project consists of five Lambda functions:

1. **initial-lambda**: Entry point for the workflow
2. **process-file-lambda**: Processes individual files
3. **aggregate-lambda**: Combines extracted text
4. **analysis-lambda**: Performs AI-powered analysis
5. **status-lambda**: Provides job status information

## Environment Variables

The Lambda functions use the following environment variables:

- `JOBS_TABLE_NAME`: DynamoDB table name for job tracking (default: MainframeAnalyzerJobs)
- `STATE_MACHINE_ARN`: ARN of the Step Functions state machine
- `MAX_FILES`: Maximum number of files to process (default: 100)
- `MAX_COMBINED_CHARS`: Maximum combined character count for analysis (default: 100000)
- `PARAMETER_STORE_PREFIX`: Prefix for parameters in Parameter Store (default: /mainframe-analyzer/)
- `BEDROCK_MODEL_ID`: Bedrock model ID to use (default: anthropic.claude-3-sonnet-20240229-v1:0)

## Troubleshooting

If you encounter any issues with the scripts, check the following:

1. Make sure you have the AWS CLI installed and configured with appropriate permissions.
2. Verify that the S3 bucket exists and you have permissions to access it.
3. Check CloudFormation stack events for deployment errors.
4. Examine CloudWatch Logs for Lambda function errors.
