# User Guide

This guide provides instructions for using the Asynchronous CloudFormation Generator to generate CloudFormation templates from resource configurations stored in S3 buckets.

## Overview

The Asynchronous CloudFormation Generator allows you to:

1. Generate CloudFormation templates from resource configurations stored in S3 buckets
2. Track the status of template generation jobs
3. Access generated templates and archived configurations

## Prerequisites

Before using the solution, ensure you have:

1. Successfully deployed the solution (see [Deployment Guide](deployment.md))
2. Access to the Amazon Bedrock console
3. Resource configurations stored in an S3 bucket
4. Appropriate permissions to access the S3 bucket and AWS services

## Using the Bedrock Agent

The easiest way to interact with the CloudFormation Generator is through the Amazon Bedrock agent:

1. Go to the Amazon Bedrock console
2. Navigate to Agents and find your deployed agent (CFNGeneratorAgent-<env>)
3. Click on the agent to open the Test window
4. Start a conversation with the agent

### Generating a Template

To generate a CloudFormation template:

1. Start a conversation with the agent
2. Request a CloudFormation template generation, for example:
   ```
   I need to generate a CloudFormation template for the resources in my S3 bucket.
   ```
3. The agent will ask for the S3 bucket name and folder path
4. Provide the requested information:
   ```
   Bucket name: my-resource-configs
   Folder path: resources/lambda
   ```
5. The agent will initiate the template generation process and provide a job ID
6. Make note of the job ID for checking the status later

### Checking Job Status

To check the status of a template generation job:

1. Ask the agent to check the status of your job:
   ```
   Can you check the status of my template generation job?
   ```
2. The agent will ask for the job ID
3. Provide the job ID:
   ```
   Job ID: 12345678-abcd-1234-efgh-123456789012
   ```
4. The agent will retrieve and display the current status of the job

### Accessing Generated Templates

Once the job is complete, you can access the generated template:

1. Check the job status as described above
2. If the status is COMPLETED, the agent will provide S3 locations for:
   - The generated CloudFormation template
   - The zipped template archive
   - The zipped configuration files archive
3. You can download these files from the S3 console or using the AWS CLI

## Direct API Usage

Advanced users can interact with the CloudFormation Generator directly through Lambda functions:

### Generating a Template

To generate a template using direct Lambda invocation:

```bash
aws lambda invoke \
  --function-name CFNGenerator-Initial-<env> \
  --payload '{"bucket_name":"my-resource-configs","s3_folder":"resources/lambda"}' \
  response.json
```

### Checking Job Status

To check the status of a job:

```bash
aws lambda invoke \
  --function-name CFNGenerator-Status-<env> \
  --payload '{"job_id":"12345678-abcd-1234-efgh-123456789012"}' \
  status.json
```

## Resource Configuration Format

The CloudFormation Generator works best with resource configurations in JSON format. Each file should represent a single AWS resource or a group of related resources.

Example resource configuration file structure:

```
resources/
├── lambda/
│   ├── function1.json
│   ├── function2.json
│   └── layer1.json
├── dynamodb/
│   └── table1.json
└── s3/
    └── bucket1.json
```

Example resource configuration file content (Lambda function):

```json
{
  "FunctionName": "MyFunction",
  "Runtime": "python3.9",
  "Handler": "index.handler",
  "Role": "arn:aws:iam::123456789012:role/lambda-role",
  "Code": {
    "S3Bucket": "my-code-bucket",
    "S3Key": "function.zip"
  },
  "Environment": {
    "Variables": {
      "ENV": "prod",
      "DEBUG": "false"
    }
  },
  "Tags": {
    "Service": "MyService",
    "Environment": "Production"
  }
}
```

## Monitoring Jobs

You can monitor template generation jobs through:

1. **DynamoDB Console**: View the job records in the CFNGeneratorJobs-<env> table
2. **Step Functions Console**: Monitor the execution of the CFNGeneratorWorkflow-<env> state machine
3. **CloudWatch Logs**: View logs from the Lambda functions for detailed information

## Troubleshooting

If you encounter issues:

1. **Job Stuck in PENDING**: Check Step Functions execution for errors
2. **Job Failed with ERROR**: Check the error message in the job record
3. **Template Generation Failed**: Check CloudWatch Logs for the Generator Lambda
4. **S3 Access Issues**: Verify IAM permissions and S3 bucket policies
5. **Bedrock Agent Not Responding**: Check Bedrock agent configuration and logs

## Best Practices

For optimal results:

1. Organize resource configurations logically in S3 folders
2. Use consistent naming conventions for resources
3. Include all necessary configuration parameters
4. Keep resource configurations up to date
5. Use JSON format for resource configurations
6. Include tags and metadata for better template organization
7. Monitor job status and review generated templates before deployment
## Job Status Values

The CloudFormation Generator uses the following status values to track job progress:

| Status | Description |
|--------|-------------|
| PENDING | Job has been created but processing hasn't started yet |
| PROCESSING | Job is actively being processed |
| VALIDATING | Template validation is in progress |
| FIXING | Attempting to fix template errors using AI |
| VALIDATED | Template has been successfully validated |
| VALIDATION_FAILED | Template validation failed after multiple fix attempts |
| COMPLETED | Job has finished successfully |
| FAILED | Job encountered an error and couldn't complete |

## Template Validation and Auto-Fixing

The CloudFormation Generator includes an intelligent validation system that:

1. Validates the syntax of generated templates
2. Validates deployment feasibility using CloudFormation change sets
3. Automatically fixes validation errors using Amazon Bedrock LLM
4. Makes multiple fix attempts (up to 5 by default) to resolve issues

When checking the status of a job, you may see:
- **VALIDATING**: The system is validating the template
- **FIXING**: The system detected errors and is using AI to fix them
- **VALIDATED**: The template passed validation
- **VALIDATION_FAILED**: The template failed validation after multiple fix attempts

If validation fails, the status response will include error details to help you understand and address the issues.
