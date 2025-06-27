# Deployment and Configuration

## Deployment

The project includes deployment scripts in the `scripts` directory:

1. **1.deploy.sh**: Deploys the CloudFormation stack
   ```bash
   ./scripts/1.deploy.sh --region us-east-1 --env dev --stack-name mainframe-transform
   ```

2. **2.update-lambda-code.sh**: Updates Lambda function code
   ```bash
   ./scripts/2.update-lambda-code.sh --region us-east-1 --env dev --function initial
   ```

3. **3.package-lambdas.sh**: Packages Lambda functions
   ```bash
   ./scripts/3.package-lambdas.sh --region us-east-1 --env dev --output ./dist
   ```

4. **4.test-workflow.sh**: Tests the workflow
   ```bash
   ./scripts/4.test-workflow.sh --region us-east-1 --bucket your-bucket --folder your-folder
   ```

## Configuration

The Lambda functions use the following environment variables:

- `JOBS_TABLE_NAME`: DynamoDB table name for job tracking
- `STATE_MACHINE_ARN`: ARN of the Step Functions state machine
- `MAX_FILES`: Maximum number of files to process
- `MAX_COMBINED_CHARS`: Maximum combined character count for analysis
- `PARAMETER_STORE_PREFIX`: Prefix for parameters in Parameter Store
- `BEDROCK_MODEL_ID`: Bedrock model ID to use

## CloudFormation Resources

The CloudFormation template creates the following resources:

1. **DynamoDB Table**: For job tracking and status management
2. **Lambda Functions**: Five Lambda functions for different processing stages
3. **IAM Roles**: With least privilege permissions for each Lambda function
4. **Step Functions State Machine**: For workflow orchestration
5. **S3 Bucket**: For storing input documents, extracted text, and analysis results

## Security Considerations

- IAM roles with least privilege permissions
- S3 bucket policies to restrict access
- DynamoDB table encryption
- Secure parameter storage in Parameter Store
- No public access to resources

## Monitoring and Logging

- CloudWatch Logs for Lambda function logs
- CloudWatch Metrics for performance monitoring
- Step Functions execution history for workflow tracking
- DynamoDB for job status tracking

## Scaling Considerations

- Lambda concurrency for parallel file processing
- DynamoDB on-demand capacity for variable workloads
- S3 for virtually unlimited storage
- Step Functions for reliable workflow orchestration

## Prerequisites

Before deploying the application, ensure you have:

1. AWS CLI installed and configured
2. Appropriate IAM permissions to create resources
3. Amazon Bedrock access configured
4. Python 3.8+ for local development

## Post-Deployment Verification

After deployment, verify the following:

1. All Lambda functions are deployed correctly
2. Step Functions state machine is created
3. DynamoDB table is created
4. IAM roles have appropriate permissions
5. Run the test workflow to verify end-to-end functionality
