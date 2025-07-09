# Deployment Guide - Mainframe Modernization Platform

## Overview

This comprehensive guide walks you through deploying the Mainframe Modernization Platform in your AWS environment. The platform supports multiple deployment scenarios from development environments to enterprise production deployments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start Deployment](#quick-start-deployment)
3. [Detailed Deployment Steps](#detailed-deployment-steps)
4. [Configuration Options](#configuration-options)
5. [Environment-Specific Deployments](#environment-specific-deployments)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance and Updates](#maintenance-and-updates)

## Prerequisites

### 1. AWS Account Requirements

#### Account Setup
- **AWS Account** with administrative access
- **AWS CLI v2.0+** installed and configured
- **Billing alerts** enabled for cost monitoring
- **Service quotas** verified for required services

#### Required AWS Services
Ensure the following services are available in your target region:
- Amazon Bedrock (with Claude models enabled)
- AWS Lambda
- Amazon S3
- Amazon DynamoDB
- AWS Step Functions
- AWS Systems Manager Parameter Store
- Amazon CloudWatch
- AWS X-Ray (optional but recommended)

#### Service Quotas to Verify
```bash
# Check Lambda concurrent executions limit
aws service-quotas get-service-quota \
  --service-code lambda \
  --quota-code L-B99A9384

# Check Bedrock model access
aws bedrock list-foundation-models \
  --region us-east-1

# Check Step Functions execution limit
aws service-quotas get-service-quota \
  --service-code states \
  --quota-code L-1B91125E
```

### 2. Local Development Environment

#### Required Tools
```bash
# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install Python 3.9+
python3 --version  # Should be 3.9 or higher

# Install Git
git --version

# Install jq for JSON processing
sudo apt-get install jq  # Ubuntu/Debian
brew install jq          # macOS
```

#### AWS CLI Configuration
```bash
# Configure AWS credentials
aws configure
# AWS Access Key ID: [Your Access Key]
# AWS Secret Access Key: [Your Secret Key]
# Default region name: us-east-1
# Default output format: json

# Verify configuration
aws sts get-caller-identity
```

### 3. Permissions Requirements

#### IAM Policy for Deployment
Create an IAM policy with the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "lambda:*",
        "s3:*",
        "dynamodb:*",
        "states:*",
        "ssm:*",
        "bedrock:*",
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PassRole",
        "iam:GetRole",
        "iam:CreatePolicy",
        "iam:DeletePolicy",
        "logs:*",
        "xray:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## Quick Start Deployment

### One-Command Deployment

For a complete platform deployment with default settings:

```bash
# Clone the repository
git clone <repository-url>
cd mainframe-modernization-platform-v3

# Deploy everything with one command
./scripts/deploy-all.sh --region us-east-1 --env dev

# Expected output:
# ✅ Validating prerequisites...
# ✅ Deploying infrastructure...
# ✅ Deploying CFN Generator service...
# ✅ Deploying Mainframe Analyzer service...
# ✅ Deploying Bedrock agents...
# ✅ Uploading sample data...
# ✅ Deployment completed successfully!
```

### Deployment Time Expectations
- **Complete Platform**: 15-25 minutes
- **Individual Services**: 5-10 minutes each
- **Bedrock Agents**: 3-5 minutes

## Detailed Deployment Steps

### Step 1: Repository Setup

```bash
# Clone and navigate to the project
git clone <repository-url>
cd mainframe-modernization-platform-v3

# Verify project structure
ls -la
# Expected directories:
# - infrastructure/
# - services/
# - scripts/
# - prompts/
# - tests/
# - docs/
```

### Step 2: Environment Configuration

#### Create Environment Configuration File
```bash
# Create environment-specific configuration
cat > config/dev.env << EOF
# Environment Configuration
ENVIRONMENT=dev
AWS_REGION=us-east-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Service Configuration
CFN_GENERATOR_MEMORY=2048
MAINFRAME_ANALYZER_MEMORY=3008
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0

# Storage Configuration
S3_BUCKET_PREFIX=mainframe-transform
DYNAMODB_BILLING_MODE=ON_DEMAND

# Monitoring Configuration
ENABLE_XRAY=true
LOG_LEVEL=INFO
EOF
```

#### Validate Configuration
```bash
# Run configuration validation
./scripts/validate-config.sh --env dev

# Expected output:
# ✅ AWS credentials configured
# ✅ Required services available
# ✅ Service quotas sufficient
# ✅ Configuration valid
```

### Step 3: Infrastructure Deployment

#### Deploy Core Infrastructure
```bash
# Deploy the main infrastructure stack
aws cloudformation deploy \
  --template-file infrastructure/main.yaml \
  --stack-name mainframe-modernization-dev \
  --parameter-overrides \
    Environment=dev \
    BucketPrefix=mainframe-transform \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# Monitor deployment progress
aws cloudformation describe-stacks \
  --stack-name mainframe-modernization-dev \
  --query 'Stacks[0].StackStatus'
```

#### Verify Infrastructure Deployment
```bash
# Check S3 bucket creation
aws s3 ls | grep mainframe-transform

# Check DynamoDB table creation
aws dynamodb list-tables | grep MainframeModernization

# Check IAM roles creation
aws iam list-roles | grep MainframeModernization
```

### Step 4: Service Deployment

#### Deploy CFN Generator Service
```bash
# Package Lambda functions
cd services/cfn-generator
zip -r cfn-generator-functions.zip src/

# Deploy service stack
aws cloudformation deploy \
  --template-file ../../infrastructure/cfn-generator-service.yaml \
  --stack-name cfn-generator-service-dev \
  --parameter-overrides \
    Environment=dev \
    CodeBucket=mainframe-transform-dev-$(aws sts get-caller-identity --query Account --output text) \
  --capabilities CAPABILITY_IAM

cd ../..
```

#### Deploy Mainframe Analyzer Service
```bash
# Package Lambda functions
cd services/mainframe-analyzer
zip -r mainframe-analyzer-functions.zip src/

# Deploy service stack
aws cloudformation deploy \
  --template-file ../../infrastructure/mainframe-analyzer-service.yaml \
  --stack-name mainframe-analyzer-service-dev \
  --parameter-overrides \
    Environment=dev \
    CodeBucket=mainframe-transform-dev-$(aws sts get-caller-identity --query Account --output text) \
  --capabilities CAPABILITY_IAM

cd ../..
```

### Step 5: Bedrock Agents Deployment

#### Enable Bedrock Models
```bash
# Check available models
aws bedrock list-foundation-models --region us-east-1

# Enable Claude models (if not already enabled)
# Note: This may require manual action in the AWS Console
echo "Ensure Claude 3 Haiku and Claude 3 Sonnet models are enabled in Bedrock console"
```

#### Deploy Bedrock Agents
```bash
# Upload agent prompts to Parameter Store
./scripts/upload-prompts.sh --env dev

# Deploy Bedrock agents
aws cloudformation deploy \
  --template-file infrastructure/bedrock-agents.yaml \
  --stack-name bedrock-agents-dev \
  --parameter-overrides \
    Environment=dev \
  --capabilities CAPABILITY_IAM
```

### Step 6: Sample Data Upload

```bash
# Upload sample mainframe documents
aws s3 cp tests/mainframe-docs/ \
  s3://mainframe-transform-dev-$(aws sts get-caller-identity --query Account --output text)/sample-docs/ \
  --recursive

# Verify upload
aws s3 ls s3://mainframe-transform-dev-$(aws sts get-caller-identity --query Account --output text)/sample-docs/
```

## Configuration Options

### Environment Variables

#### Lambda Function Configuration
```yaml
# In infrastructure templates
Environment:
  Variables:
    LOG_LEVEL: !Ref LogLevel
    BEDROCK_MODEL_ID: !Ref BedrockModelId
    S3_BUCKET: !Ref S3Bucket
    DYNAMODB_TABLE: !Ref DynamoDBTable
    ENABLE_XRAY: !Ref EnableXRay
```

#### Parameter Store Configuration
```bash
# Set configuration parameters
aws ssm put-parameter \
  --name "/mainframe-modernization/cfn-generator/dev/bedrock-model-id" \
  --value "anthropic.claude-3-sonnet-20240229-v1:0" \
  --type "String"

aws ssm put-parameter \
  --name "/mainframe-modernization/mainframe-analyzer/dev/bedrock-model-id" \
  --value "anthropic.claude-3-haiku-20240307-v1:0" \
  --type "String"
```

### Resource Sizing Options

#### Lambda Memory Configuration
```yaml
# Small deployment (development)
LambdaMemoryConfig:
  Initial: 1024
  Processor: 2048
  Analysis: 2048

# Medium deployment (staging)
LambdaMemoryConfig:
  Initial: 1024
  Processor: 3008
  Analysis: 3008

# Large deployment (production)
LambdaMemoryConfig:
  Initial: 1536
  Processor: 3008
  Analysis: 3008
```

#### DynamoDB Configuration
```yaml
# Development environment
DynamoDBConfig:
  BillingMode: ON_DEMAND
  PointInTimeRecovery: false

# Production environment
DynamoDBConfig:
  BillingMode: PROVISIONED
  ReadCapacityUnits: 100
  WriteCapacityUnits: 50
  PointInTimeRecovery: true
```

## Environment-Specific Deployments

### Development Environment

#### Characteristics
- Cost-optimized configuration
- Minimal monitoring
- Sample data included
- Relaxed security settings

#### Deployment Command
```bash
./scripts/deploy-all.sh \
  --region us-east-1 \
  --env dev \
  --config-file config/dev.yaml \
  --enable-samples true
```

#### Configuration File (config/dev.yaml)
```yaml
Environment: dev
Region: us-east-1

Lambda:
  Memory:
    Initial: 1024
    Processor: 2048
    Analysis: 2048
  Timeout:
    Initial: 300
    Processor: 900
    Analysis: 900

DynamoDB:
  BillingMode: ON_DEMAND
  PointInTimeRecovery: false

S3:
  VersioningEnabled: false
  LifecyclePolicies: true

Monitoring:
  XRayEnabled: false
  DetailedMetrics: false
  LogRetention: 7
```

### Staging Environment

#### Characteristics
- Production-like configuration
- Enhanced monitoring
- Performance testing ready
- Security hardening

#### Deployment Command
```bash
./scripts/deploy-all.sh \
  --region us-east-1 \
  --env staging \
  --config-file config/staging.yaml \
  --enable-monitoring true
```

#### Configuration File (config/staging.yaml)
```yaml
Environment: staging
Region: us-east-1

Lambda:
  Memory:
    Initial: 1024
    Processor: 3008
    Analysis: 3008
  Timeout:
    Initial: 300
    Processor: 900
    Analysis: 900
  ReservedConcurrency:
    Processor: 50
    Analysis: 25

DynamoDB:
  BillingMode: ON_DEMAND
  PointInTimeRecovery: true

S3:
  VersioningEnabled: true
  LifecyclePolicies: true
  CrossRegionReplication: false

Monitoring:
  XRayEnabled: true
  DetailedMetrics: true
  LogRetention: 30
  AlarmsEnabled: true
```

### Production Environment

#### Characteristics
- High availability configuration
- Comprehensive monitoring
- Security hardening
- Multi-region support (optional)

#### Deployment Command
```bash
./scripts/deploy-all.sh \
  --region us-east-1 \
  --env prod \
  --config-file config/prod.yaml \
  --enable-monitoring true \
  --enable-backup true
```

#### Configuration File (config/prod.yaml)
```yaml
Environment: prod
Region: us-east-1

Lambda:
  Memory:
    Initial: 1536
    Processor: 3008
    Analysis: 3008
  Timeout:
    Initial: 300
    Processor: 900
    Analysis: 900
  ReservedConcurrency:
    Processor: 100
    Analysis: 50
  ProvisionedConcurrency:
    Initial: 5

DynamoDB:
  BillingMode: PROVISIONED
  ReadCapacityUnits: 100
  WriteCapacityUnits: 50
  PointInTimeRecovery: true
  BackupEnabled: true

S3:
  VersioningEnabled: true
  LifecyclePolicies: true
  CrossRegionReplication: true
  ReplicationRegion: us-west-2

Monitoring:
  XRayEnabled: true
  DetailedMetrics: true
  LogRetention: 90
  AlarmsEnabled: true
  DashboardEnabled: true

Security:
  VPCEnabled: true
  KMSEncryption: true
  WAFEnabled: true
```

## Post-Deployment Verification

### Automated Verification

#### Run Deployment Validation Script
```bash
# Comprehensive deployment validation
./scripts/validate-deployment.sh --env dev

# Expected output:
# ✅ Infrastructure stack deployed successfully
# ✅ CFN Generator service operational
# ✅ Mainframe Analyzer service operational
# ✅ Bedrock agents configured correctly
# ✅ Sample data uploaded successfully
# ✅ All health checks passed
```

### Manual Verification Steps

#### 1. Test CFN Generator Service
```bash
# Test CFN Generator via direct Lambda invocation
aws lambda invoke \
  --function-name CFNGenerator-Initial-dev \
  --payload '{
    "bucket_name": "mainframe-transform-dev-'$(aws sts get-caller-identity --query Account --output text)'",
    "s3_folder": "sample-configs"
  }' \
  response.json

# Check response
cat response.json
```

#### 2. Test Mainframe Analyzer Service
```bash
# Test Mainframe Analyzer via direct Lambda invocation
aws lambda invoke \
  --function-name MainframeAnalyzer-Initial-dev \
  --payload '{
    "bucket_name": "mainframe-transform-dev-'$(aws sts get-caller-identity --query Account --output text)'",
    "s3_folder": "sample-docs"
  }' \
  response.json

# Check response
cat response.json
```

#### 3. Test Bedrock Agents
```bash
# List deployed agents
aws bedrock-agent list-agents --region us-east-1

# Test agent via AWS Console
echo "Navigate to Bedrock Console > Agents > Test your deployed Supervisor Agent"
```

#### 4. Verify Monitoring Setup
```bash
# Check CloudWatch log groups
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/CFNGenerator"

aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/MainframeAnalyzer"

# Check X-Ray traces (if enabled)
aws xray get-trace-summaries \
  --time-range-type TimeRangeByStartTime \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S)
```

### Health Check Endpoints

#### Create Health Check Function
```python
# health-check.py
import boto3
import json

def check_service_health():
    """Comprehensive health check for all services"""
    
    results = {
        "cfn_generator": check_cfn_generator(),
        "mainframe_analyzer": check_mainframe_analyzer(),
        "bedrock_agents": check_bedrock_agents(),
        "infrastructure": check_infrastructure()
    }
    
    return results

def check_cfn_generator():
    """Check CFN Generator service health"""
    lambda_client = boto3.client('lambda')
    
    try:
        response = lambda_client.invoke(
            FunctionName='CFNGenerator-Status-dev',
            Payload=json.dumps({"health_check": True})
        )
        return {"status": "healthy", "response_code": response['StatusCode']}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# Run health check
if __name__ == "__main__":
    health_status = check_service_health()
    print(json.dumps(health_status, indent=2))
```

## Troubleshooting

### Common Deployment Issues

#### 1. CloudFormation Stack Failures

**Issue**: Stack deployment fails with resource creation errors
```bash
# Check stack events for detailed error information
aws cloudformation describe-stack-events \
  --stack-name mainframe-modernization-dev \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

**Common Solutions**:
- **IAM Permissions**: Ensure deployment role has sufficient permissions
- **Service Quotas**: Check if service limits are exceeded
- **Resource Names**: Verify resource names are unique and follow naming conventions

#### 2. Lambda Function Deployment Issues

**Issue**: Lambda functions fail to deploy or update
```bash
# Check Lambda function configuration
aws lambda get-function-configuration \
  --function-name CFNGenerator-Initial-dev

# Check Lambda function logs
aws logs tail /aws/lambda/CFNGenerator-Initial-dev --follow
```

**Common Solutions**:
- **Package Size**: Ensure deployment package is under 50MB
- **Runtime Compatibility**: Verify Python version compatibility
- **Dependencies**: Check all required dependencies are included

#### 3. Bedrock Access Issues

**Issue**: Bedrock model access denied
```bash
# Check available models
aws bedrock list-foundation-models --region us-east-1

# Check model access
aws bedrock get-foundation-model \
  --model-identifier anthropic.claude-3-haiku-20240307-v1:0
```

**Common Solutions**:
- **Model Access**: Request access to Claude models in Bedrock console
- **Region Availability**: Ensure models are available in deployment region
- **Service Quotas**: Check Bedrock service quotas

#### 4. S3 Access Issues

**Issue**: S3 bucket access denied or not found
```bash
# Check bucket existence and permissions
aws s3 ls s3://mainframe-transform-dev-$(aws sts get-caller-identity --query Account --output text)

# Check bucket policy
aws s3api get-bucket-policy \
  --bucket mainframe-transform-dev-$(aws sts get-caller-identity --query Account --output text)
```

**Common Solutions**:
- **Bucket Naming**: Ensure bucket names are globally unique
- **Region Consistency**: Verify bucket and services are in same region
- **IAM Policies**: Check Lambda execution roles have S3 access

### Debugging Tools

#### 1. CloudFormation Drift Detection
```bash
# Detect configuration drift
aws cloudformation detect-stack-drift \
  --stack-name mainframe-modernization-dev

# Get drift detection results
aws cloudformation describe-stack-drift-detection-status \
  --stack-drift-detection-id <detection-id>
```

#### 2. Lambda Function Testing
```bash
# Test Lambda function locally using SAM
sam local invoke CFNGeneratorInitial \
  --event tests/events/cfn-generator-event.json

# Test with different payloads
sam local invoke MainframeAnalyzerInitial \
  --event tests/events/mainframe-analyzer-event.json
```

#### 3. Step Functions Execution Debugging
```bash
# List Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:account:stateMachine:CFNGenerator-dev

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn <execution-arn>

# Get execution history
aws stepfunctions get-execution-history \
  --execution-arn <execution-arn>
```

### Log Analysis

#### Centralized Logging Query
```bash
# Query CloudWatch Insights for errors across all services
aws logs start-query \
  --log-group-names \
    "/aws/lambda/CFNGenerator-Initial-dev" \
    "/aws/lambda/MainframeAnalyzer-Initial-dev" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc'
```

## Maintenance and Updates

### Regular Maintenance Tasks

#### 1. Update Lambda Functions
```bash
# Update function code
aws lambda update-function-code \
  --function-name CFNGenerator-Initial-dev \
  --zip-file fileb://cfn-generator-functions.zip

# Update function configuration
aws lambda update-function-configuration \
  --function-name CFNGenerator-Initial-dev \
  --memory-size 2048 \
  --timeout 600
```

#### 2. Update Bedrock Agent Prompts
```bash
# Update prompts in Parameter Store
./scripts/upload-prompts.sh --env dev --update

# Update agent configuration
aws bedrock-agent update-agent \
  --agent-id <agent-id> \
  --agent-name "MainframeModernization-Supervisor-dev" \
  --instruction "$(cat prompts/supervisor-instructions.txt)"
```

#### 3. Monitor and Optimize Costs
```bash
# Generate cost report
aws ce get-cost-and-usage \
  --time-period Start=2025-07-01,End=2025-07-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# Optimize Lambda memory settings based on usage
./scripts/optimize-lambda-memory.sh --env dev
```

### Backup and Recovery

#### 1. Configuration Backup
```bash
# Backup CloudFormation templates
aws s3 sync infrastructure/ \
  s3://mainframe-transform-dev-backup/infrastructure/

# Backup Parameter Store configuration
aws ssm get-parameters-by-path \
  --path "/mainframe-modernization" \
  --recursive > parameter-store-backup.json
```

#### 2. Data Backup
```bash
# Enable S3 versioning and cross-region replication
aws s3api put-bucket-versioning \
  --bucket mainframe-transform-dev-$(aws sts get-caller-identity --query Account --output text) \
  --versioning-configuration Status=Enabled

# Enable DynamoDB point-in-time recovery
aws dynamodb update-continuous-backups \
  --table-name MainframeModernization-Jobs-dev \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
```

### Version Management

#### 1. Semantic Versioning
```bash
# Tag releases
git tag -a v1.0.0 -m "Initial production release"
git push origin v1.0.0

# Deploy specific version
./scripts/deploy-all.sh \
  --region us-east-1 \
  --env prod \
  --version v1.0.0
```

#### 2. Rollback Procedures
```bash
# Rollback CloudFormation stack
aws cloudformation cancel-update-stack \
  --stack-name mainframe-modernization-prod

# Rollback to previous Lambda version
aws lambda update-function-code \
  --function-name CFNGenerator-Initial-prod \
  --zip-file fileb://previous-version.zip
```

This deployment guide provides comprehensive instructions for deploying and maintaining the Mainframe Modernization Platform across different environments and scenarios. Follow the appropriate sections based on your specific deployment requirements and environment constraints.
