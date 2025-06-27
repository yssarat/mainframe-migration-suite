# CloudFormation Templates

This directory contains CloudFormation templates for deploying the Mainframe Modernization Project.

## Templates

### main.yaml

The main CloudFormation template that deploys the core infrastructure for the Mainframe Modernization Project, including:

- Lambda functions for processing mainframe documentation
- Step Functions state machine for workflow orchestration
- DynamoDB table for job tracking
- IAM roles and policies

### bedrock-agent.yaml

A separate CloudFormation template for deploying the Amazon Bedrock agent that provides a conversational interface to the Mainframe Modernization Project. This template includes:

- Bedrock agent configuration
- Action groups for StartAnalysis and CheckStatus operations
- Lambda functions for handling agent requests
- IAM roles and policies for Bedrock integration
- Agent alias for versioning

## Deployment

To deploy the main infrastructure:

```bash
cd scripts
./1.deploy.sh --region us-east-1 --env dev --stack-name mainframe-transform
```

To deploy the Bedrock agent:

```bash
aws cloudformation deploy \
  --template-file ../cloudformation/bedrock-agent.yaml \
  --stack-name mainframe-transform-bedrock-agent \
  --parameter-overrides Environment=dev FoundationModelId=anthropic.claude-3-5-haiku-20241022-v1:0 \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

## Parameters

### main.yaml Parameters

- `Environment`: Environment (dev or prod)
- `S3BucketName`: S3 bucket name for storing input documents and analysis results

### bedrock-agent.yaml Parameters

- `Environment`: Environment (dev or prod)
- `FoundationModelId`: Bedrock foundation model ID to use for the agent

## Resources

The templates create the following resources:

- Lambda functions for processing mainframe documentation
- Step Functions state machine for workflow orchestration
- DynamoDB table for job tracking
- IAM roles and policies
- Bedrock agent with action groups
- Bedrock agent alias

## Outputs

The templates provide the following outputs:

- Lambda function ARNs
- Step Functions state machine ARN
- DynamoDB table name
- Bedrock agent ID and ARN
- Bedrock agent alias ID
