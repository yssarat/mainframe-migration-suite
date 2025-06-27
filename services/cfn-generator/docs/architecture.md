# Architecture Overview

The Asynchronous CloudFormation Generator is designed as a serverless application that processes resource configurations stored in S3 buckets and generates CloudFormation templates. The architecture follows AWS best practices for security, reliability, and operational excellence.

## Architecture Diagram

![Architecture Diagram](architecture-diagram.png)

## Components

### 1. Amazon Bedrock Agent

- Provides a natural language interface for users to request CloudFormation template generation
- Integrates with Lambda functions through action groups
- Handles user interactions and provides status updates

### 2. AWS Lambda Functions

- **Initial Lambda**: Validates input parameters, creates job records, and initiates the Step Functions workflow
- **Status Lambda**: Retrieves job status information from DynamoDB
- **Validation Lambda**: Validates CloudFormation templates and automatically fixes errors using Bedrock LLM
- **Generator Lambda**: Processes resource configurations and generates CloudFormation templates
- **Completion Lambda**: Finalizes job processing and updates job status

### 3. Amazon DynamoDB

- Stores job metadata and status information
- Enables tracking of asynchronous job processing
- Provides a persistent record of all template generation requests

### 4. AWS Step Functions

- Orchestrates the asynchronous workflow
- Manages state transitions and error handling
- Provides visibility into job execution status

### 5. Amazon S3

- Stores input resource configurations
- Stores generated CloudFormation templates
- Archives processed configurations and templates

### 6. AWS Systems Manager Parameter Store

- Stores prompt templates for CloudFormation generation
- Enables centralized management of configuration parameters

## Data Flow

1. User requests CloudFormation template generation through the Bedrock agent
2. Bedrock agent invokes the Initial Lambda function with the S3 bucket and folder path
3. Initial Lambda validates input parameters and creates a job record in DynamoDB
4. Initial Lambda starts the Step Functions workflow
5. Step Functions executes the Generator Lambda to process resource configurations
6. Generator Lambda retrieves resource configurations from S3 and generates the CloudFormation template
7. Generator Lambda uploads the template to S3
8. Validation Lambda validates the template and automatically fixes any errors using Bedrock LLM
9. Completion Lambda updates the job status in DynamoDB and archives the configurations
10. User can check job status through the Bedrock agent, which invokes the Status Lambda
11. Status Lambda retrieves job status from DynamoDB and returns it to the user

## Security Considerations

- IAM roles follow the principle of least privilege
- S3 buckets are configured with appropriate access controls
- DynamoDB tables use encryption at rest
- Lambda functions run in VPC with appropriate security groups (optional)
- All API communications use HTTPS

## Scalability

- Lambda functions automatically scale based on demand
- DynamoDB uses on-demand capacity for automatic scaling
- Step Functions can handle multiple concurrent executions
- S3 provides virtually unlimited storage capacity

## Monitoring and Logging

- CloudWatch Logs capture Lambda function logs
- CloudWatch Metrics track function invocations and errors
- X-Ray provides distributed tracing (optional)
- CloudTrail logs API calls for auditing

## Error Handling

- Step Functions include retry logic for transient failures
- DLQ (Dead Letter Queue) captures failed Lambda invocations
- Error states in Step Functions workflow handle exceptions
- Comprehensive error messages are stored in job records
