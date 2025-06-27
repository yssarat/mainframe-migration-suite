# Deployment Guide - Mainframe Modernization Platform

## Overview

This guide provides comprehensive instructions for deploying the Mainframe Modernization Platform, which consists of three main components:

1. **Bedrock Agents** - AI orchestration layer with Supervisor, CFN Generator, and Mainframe Analyzer agents
2. **CloudFormation Generator Service** - Converts resource configurations to CloudFormation templates
3. **Mainframe Analyzer Service** - Analyzes mainframe documentation for modernization recommendations

## Prerequisites

### AWS Account Requirements
- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Permissions to create:
  - Lambda functions
  - Step Functions
  - DynamoDB tables
  - S3 buckets
  - IAM roles and policies
  - Bedrock agents
  - CloudFormation stacks

### Local Environment
- Python 3.9 or higher
- Git
- Bash shell (for deployment scripts)

### AWS CLI Configuration
```bash
# Configure AWS CLI
aws configure

# Verify configuration
aws sts get-caller-identity
```

## Infrastructure Organization

The platform uses a centralized infrastructure approach:

```
infrastructure/
├── main.yaml                                    # Master deployment template
├── combined-mainframe-modernization-agents.yaml # Bedrock agents
├── cfn-generator-service.yaml                   # CFN Generator service
└── mainframe-analyzer-service.yaml             # Mainframe Analyzer service
```

## Deployment Options

### Option 1: Complete Platform Deployment (Recommended)

Deploy all components with a single command:

```bash
cd mainframe-modernization-platform
./scripts/deploy-all.sh --region us-east-1 --env dev
```

**Parameters:**
- `--region`: AWS region (required)
- `--env`: Environment (dev, staging, prod) [default: dev]
- `--stack-name`: Custom stack name prefix [default: mainframe-modernization-platform]
- `--profile`: AWS profile to use [optional]

**Example:**
```bash
./scripts/deploy-all.sh \
  --region us-west-2 \
  --env prod \
  --stack-name my-modernization-platform \
  --profile production
```

### Option 2: Individual Service Deployment

Deploy specific components independently:

#### Deploy Bedrock Agents Only
```bash
./scripts/deploy-service.sh \
  --service bedrock-agents \
  --region us-east-1 \
  --env dev
```

#### Deploy CFN Generator Service
```bash
./scripts/deploy-service.sh \
  --service cfn-generator \
  --region us-east-1 \
  --env dev
```

#### Deploy Mainframe Analyzer Service
```bash
./scripts/deploy-service.sh \
  --service mainframe-analyzer \
  --region us-east-1 \
  --env dev
```

### Option 3: Manual CloudFormation Deployment

For advanced users who prefer direct CloudFormation control:

```bash
# Deploy master template
aws cloudformation deploy \
  --template-file infrastructure/main.yaml \
  --stack-name mainframe-modernization-platform-dev \
  --parameter-overrides \
    Environment=dev \
    FoundationModel=anthropic.claude-3-5-haiku-20241022-v1:0 \
    DeployServices=both \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

## Deployment Process

### Step 1: Pre-deployment Validation

Run the validation script to check for issues:

```bash
./scripts/validate-deployment.sh
```

This script checks for:
- Hardcoded account numbers
- CloudFormation template validity
- Required files and permissions
- AWS CLI configuration

### Step 2: Lambda Code Packaging

The deployment scripts automatically handle Lambda code packaging, but you can also do it manually:

```bash
# CFN Generator Lambda functions
cd services/cfn-generator
./scripts/deploy.sh --package-only --env dev --region us-east-1

# Mainframe Analyzer Lambda functions
cd services/mainframe-analyzer
./scripts/3.package-lambdas.sh --region us-east-1 --env dev
```

### Step 3: Infrastructure Deployment

The deployment creates the following AWS resources:

#### Bedrock Agents Stack
- Supervisor Agent (coordinates between services)
- CFN Generator Agent (handles template generation requests)
- Mainframe Analyzer Agent (handles analysis requests)
- Agent aliases and collaboration configuration

#### CFN Generator Service Stack
- Lambda functions (Initial, Generator, Validation, Completion, Status)
- Step Functions workflow
- DynamoDB table for job tracking
- S3 bucket for templates and configurations
- IAM roles and policies

#### Mainframe Analyzer Service Stack
- Lambda functions (Initial, ProcessFile, Aggregate, Analysis, Status, etc.)
- Step Functions workflow with parallel processing
- DynamoDB table for job tracking
- S3 bucket for documents and results
- IAM roles and policies

### Step 4: Post-deployment Verification

After deployment, verify the platform is working:

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name mainframe-modernization-platform-dev \
  --region us-east-1

# Test Bedrock agents
# Navigate to Bedrock console > Agents > Test your supervisor agent
```

## Configuration Parameters

### Environment-specific Settings

The platform supports multiple environments with different configurations:

```yaml
# Development Environment
Environment: dev
FoundationModel: anthropic.claude-3-5-haiku-20241022-v1:0
IdleSessionTTL: 600

# Production Environment  
Environment: prod
FoundationModel: anthropic.claude-3-5-haiku-20241022-v1:0
IdleSessionTTL: 1800
```

### Foundation Model Options

Supported Bedrock foundation models:
- `anthropic.claude-3-5-haiku-20241022-v1:0` (recommended, cost-effective)
- `anthropic.claude-3-5-sonnet-20241022-v1:0` (higher capability)
- `anthropic.claude-3-opus-20240229-v1:0` (highest capability)

### Service Deployment Options

Control which services to deploy:
- `both` - Deploy all services (default)
- `cfn-generator` - Deploy only CFN Generator
- `mainframe-analyzer` - Deploy only Mainframe Analyzer  
- `agents-only` - Deploy only Bedrock agents

## Troubleshooting

### Common Issues

#### 1. Permission Errors
```
Error: User is not authorized to perform: bedrock:CreateAgent
```
**Solution:** Ensure your AWS user/role has the required permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:*",
        "lambda:*",
        "iam:*",
        "s3:*",
        "dynamodb:*",
        "states:*",
        "cloudformation:*"
      ],
      "Resource": "*"
    }
  ]
}
```

#### 2. Stack Already Exists
```
Error: Stack already exists
```
**Solution:** Update the existing stack or delete it first:
```bash
aws cloudformation delete-stack \
  --stack-name mainframe-modernization-platform-dev \
  --region us-east-1
```

#### 3. Lambda Code Bucket Issues
```
Error: S3 bucket does not exist
```
**Solution:** The deployment scripts create buckets automatically. If issues persist:
```bash
# Manually create bucket
aws s3 mb s3://cfn-generator-dev-$(aws sts get-caller-identity --query Account --output text)-us-east-1
```

#### 4. Bedrock Model Access
```
Error: Could not access foundation model
```
**Solution:** Enable model access in Bedrock console:
1. Go to Bedrock console
2. Navigate to Model access
3. Enable access to Claude models

### Debugging Steps

1. **Check CloudFormation Events:**
```bash
aws cloudformation describe-stack-events \
  --stack-name mainframe-modernization-platform-dev \
  --region us-east-1
```

2. **Check Lambda Logs:**
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/"
aws logs tail /aws/lambda/CFNGenerator-Initial-dev --follow
```

3. **Validate Templates:**
```bash
aws cloudformation validate-template \
  --template-body file://infrastructure/main.yaml
```

## Monitoring and Maintenance

### CloudWatch Monitoring

The platform creates CloudWatch log groups for all Lambda functions:
- `/aws/lambda/CFNGenerator-*`
- `/aws/lambda/MainframeAnalyzer-*`
- `/aws/bedrock/agents/*`

### Cost Optimization

- Use inference profiles for cost-effective Bedrock access
- Set appropriate S3 lifecycle policies
- Monitor Lambda execution costs
- Use reserved concurrency if needed

### Updates and Maintenance

To update the platform:

```bash
# Update all services
./scripts/deploy-all.sh --region us-east-1 --env dev

# Update specific service
./scripts/deploy-service.sh --service cfn-generator --region us-east-1 --env dev
```

## Security Considerations

### IAM Roles and Policies
- All services use least-privilege IAM roles
- Cross-service access is controlled via IAM policies
- No hardcoded credentials in code

### Data Encryption
- All S3 data encrypted at rest
- DynamoDB tables use encryption
- All API calls use HTTPS/TLS

### Network Security
- Services can be deployed in VPC for additional isolation
- Security groups control network access
- VPC endpoints available for AWS service access

## Next Steps

After successful deployment:

1. **Test the Platform:**
   - Navigate to Bedrock console
   - Test the Supervisor Agent
   - Try sample interactions

2. **Upload Sample Data:**
   - Upload resource configurations to S3
   - Upload mainframe documentation to S3

3. **Monitor Usage:**
   - Check CloudWatch logs
   - Monitor costs in Cost Explorer
   - Set up CloudWatch alarms

4. **Scale as Needed:**
   - Adjust Lambda memory/timeout settings
   - Configure provisioned concurrency
   - Set up additional environments

For detailed usage instructions, see the [User Guide](../README.md#usage).
