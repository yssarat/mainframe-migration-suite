# Deployment Guide

This guide provides instructions for deploying the Asynchronous CloudFormation Generator to your AWS account.

## Prerequisites

Before deploying the solution, ensure you have the following:

1. **AWS CLI**: Installed and configured with appropriate permissions
2. **Python 3.9+**: Required for local development and testing
3. **AWS Account**: With permissions to create the following resources:
   - AWS Lambda functions
   - Amazon DynamoDB tables
   - AWS Step Functions state machines
   - Amazon S3 buckets
   - AWS IAM roles and policies
   - Amazon Bedrock agents
4. **Amazon Bedrock Access**: Ensure you have access to Amazon Bedrock and the required foundation models

## Deployment Steps

### Option 1: Using the Deployment Script

The easiest way to deploy the solution is using the provided deployment script:

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd cfn-generator-project
   ```

2. Make the deployment script executable:
   ```bash
   chmod +x scripts/deploy.sh
   ```

3. Run the deployment script:
   ```bash
   ./scripts/deploy.sh --env dev --region us-east-1
   ```

   Available options:
   - `--env`: Environment (dev or prod, default: dev)
   - `--region`: AWS region (default: your configured AWS CLI region)
   - `--stack-name`: Base name for CloudFormation stacks (default: cfn-generator)

4. The script will:
   - Create an S3 bucket for Lambda code if it doesn't exist
   - Package and upload Lambda functions
   - Deploy the main CloudFormation stack
   - Deploy the Bedrock agent stack
   - Output important resource information

### Option 2: Manual Deployment

If you prefer to deploy the solution manually:

1. Create an S3 bucket for Lambda code:
   ```bash
   aws s3 mb s3://cfn-generator-<env>-<account-id>-<region>
   aws s3api put-bucket-versioning --bucket cfn-generator-<env>-<account-id>-<region> --versioning-configuration Status=Enabled
   ```

2. Package Lambda functions:
   ```bash
   cd src
   zip -r ../dist/initial-lambda.zip initial_lambda.py
   zip -r ../dist/status-lambda.zip status_lambda.py
   zip -r ../dist/generator-lambda.zip lambda_function.py
   zip -r ../dist/completion-lambda.zip completion_lambda.py
   cd ..
   ```

3. Upload Lambda packages to S3:
   ```bash
   aws s3 cp dist/initial-lambda.zip s3://cfn-generator-<env>-<account-id>-<region>/lambda/initial-lambda.zip
   aws s3 cp dist/status-lambda.zip s3://cfn-generator-<env>-<account-id>-<region>/lambda/status-lambda.zip
   aws s3 cp dist/generator-lambda.zip s3://cfn-generator-<env>-<account-id>-<region>/lambda/generator-lambda.zip
   aws s3 cp dist/completion-lambda.zip s3://cfn-generator-<env>-<account-id>-<region>/lambda/completion-lambda.zip
   ```

4. Deploy the main CloudFormation stack:
   ```bash
   aws cloudformation deploy \
     --template-file cloudformation/main.yaml \
     --stack-name cfn-generator-<env> \
     --parameter-overrides Environment=<env> \
     --capabilities CAPABILITY_IAM \
     --region <region>
   ```

5. Get outputs from the main stack:
   ```bash
   aws cloudformation describe-stacks --stack-name cfn-generator-<env> --query "Stacks[0].Outputs" --output json
   ```

6. Deploy the Bedrock agent stack:
   ```bash
   aws cloudformation deploy \
     --template-file cloudformation/bedrock-agent.yaml \
     --stack-name cfn-generator-<env>-agent \
     --parameter-overrides \
       Environment=<env> \
       InitialLambdaArn=<initial-lambda-arn> \
       StatusLambdaArn=<status-lambda-arn> \
     --capabilities CAPABILITY_IAM \
     --region <region>
   ```

## Post-Deployment Configuration

After deploying the solution, you need to configure the Bedrock agent:

1. Go to the Amazon Bedrock console
2. Navigate to Agents and find your deployed agent (CFNGeneratorAgent-<env>)
3. Test the agent using the Test window
4. Prepare an S3 bucket with resource configurations for testing
5. Use the agent to generate CloudFormation templates

## Verification

To verify that the deployment was successful:

1. Check that all CloudFormation stacks were created successfully
2. Verify that the Lambda functions are deployed and configured correctly
3. Test the Bedrock agent by asking it to generate a CloudFormation template
4. Monitor the Step Functions execution to ensure the workflow completes successfully
5. Check the S3 bucket for the generated CloudFormation template

## Troubleshooting

If you encounter issues during deployment:

1. Check CloudFormation stack events for error messages
2. Review CloudWatch Logs for Lambda function errors
3. Verify IAM permissions for the Lambda execution roles
4. Ensure Amazon Bedrock service access is properly configured
5. Check that the S3 bucket for Lambda code is accessible

## Cleanup

To remove the deployed resources:

1. Delete the Bedrock agent stack:
   ```bash
   aws cloudformation delete-stack --stack-name cfn-generator-<env>-agent --region <region>
   ```

2. Delete the main stack:
   ```bash
   aws cloudformation delete-stack --stack-name cfn-generator-<env> --region <region>
   ```

3. Delete the S3 bucket for Lambda code:
   ```bash
   aws s3 rb s3://cfn-generator-<env>-<account-id>-<region> --force
   ```
